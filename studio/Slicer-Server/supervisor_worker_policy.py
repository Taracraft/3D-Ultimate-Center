"""Explicit Linux/amd64 Supervisor worker confinement; no Compose fallback.

Landlock ABI 6 confines filesystem access, signals and abstract Unix peers.
A second inherited seccomp filter denies creation/use of every socket family,
external-process memory/FD access, alternate IPC and namespace transitions.
Only a freshly exec'd, single-threaded, capability-free worker may apply it.
The network-visible API must remain outside this Landlock domain and keep its
private configuration outside the worker's granted filesystem trees.

This module does not run an engine, configure a host, or grant publication.
"""
from __future__ import annotations

import ctypes as C
import errno
import os
from pathlib import Path
import platform
import socket
import stat
import sys

PROFILE = "supervisor-landlock-seccomp"
CANARY = Path("/data/private/isolation-canary")
CANARY_BYTES = b"ultimate-slicer-public-isolation-canary\n"
MIN_LANDLOCK_ABI = 6
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
PR_GET_DUMPABLE = 3
PR_SET_DUMPABLE = 4

# x86_64 Linux UAPI; unsupported architectures fail before any syscall.
NR_LANDLOCK_CREATE = 444
NR_LANDLOCK_ADD = 445
NR_LANDLOCK_RESTRICT = 446
FS_EXECUTE = 1 << 0
FS_WRITE = 1 << 1
FS_READ = 1 << 2
FS_READ_DIR = 1 << 3
FS_REMOVE_DIR = 1 << 4
FS_REMOVE_FILE = 1 << 5
FS_MAKE_DIR = 1 << 7
FS_MAKE_REG = 1 << 8
FS_MAKE_SYM = 1 << 12
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14
HANDLED_FS = (1 << 16) - 1
READ_TREE = FS_READ | FS_READ_DIR
READ_EXEC_TREE = READ_TREE | FS_EXECUTE
WRITE_TREE = (READ_TREE | FS_WRITE | FS_REMOVE_DIR | FS_REMOVE_FILE |
              FS_MAKE_DIR | FS_MAKE_REG | FS_MAKE_SYM | FS_REFER | FS_TRUNCATE)
READ_EXEC_PATHS = ("/usr", "/opt", "/engine")
READ_ONLY_PATHS = ("/etc", "/proc", "/sys")
WRITE_PATHS = ("/data/state", "/data/profiles", "/tmp", "/dev/shm")
DEVICE_FILES = ("/dev/null", "/dev/zero", "/dev/random", "/dev/urandom")

# Explicit amd64 numbers, including all socket operations and the old System V
# IPC syscalls. io_uring and foreign FD retrieval cannot bypass socket bans.
DENIED_SYSCALLS = frozenset({
    29, 30, 31, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    64, 65, 66, 67, 68, 69, 70, 71, 101, 155, 161, 165, 166, 220, 272,
    288, 298, 299, 304, 307, 308, 310, 311, 321, 323, 425, 426, 427, 438,
})
CLONE_NAMESPACE_FLAGS = 0x7E020000


class PolicyError(RuntimeError):
    """Stable diagnostic code; never include a supplied path or secret."""


class Ruleset(C.Structure):
    _fields_ = [("handled_access_fs", C.c_uint64),
                ("handled_access_net", C.c_uint64), ("scoped", C.c_uint64)]


class PathRule(C.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", C.c_uint64), ("parent_fd", C.c_int32)]


class Filter(C.Structure):
    _fields_ = [("code", C.c_uint16), ("jt", C.c_uint8),
                ("jf", C.c_uint8), ("k", C.c_uint32)]


class Program(C.Structure):
    _fields_ = [("length", C.c_uint16), ("filters", C.POINTER(Filter))]


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PolicyError(code)


def libc():
    require(sys.platform == "linux" and platform.machine() == "x86_64"
            and sys.maxsize > 2**32 and sys.byteorder == "little",
            "app_platform_unsupported")
    lib = C.CDLL(None, use_errno=True)
    lib.syscall.restype = C.c_long
    lib.prctl.restype = C.c_int
    return lib


def kernel_status() -> dict:
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        fields[key] = value.strip()
    return {"uids": [int(x) for x in fields["Uid"].split()],
            "caps": {key: int(fields[key], 16) for key in
                     ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")},
            "no_new_privileges": int(fields["NoNewPrivs"]),
            "seccomp": int(fields["Seccomp"]),
            "seccomp_filters": int(fields.get("Seccomp_filters", "0")),
            "threads": int(fields["Threads"])}


def _require_base(status: dict, *, single_threaded: bool) -> None:
    require(len(status["uids"]) == 4 and len(set(status["uids"])) == 1
            and status["uids"][0] == 65532, "app_worker_uid_invalid")
    require(set(status["caps"]) == {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"}
            and not any(status["caps"].values()), "app_worker_capabilities_present")
    require(status["seccomp"] == 2, "app_container_seccomp_missing")
    if single_threaded:
        require(status["threads"] == 1, "app_worker_already_multithreaded")


def _canary_identity() -> None:
    for directory in (Path("/data"), CANARY.parent):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                and stat.S_IMODE(info.st_mode) == 0o755,
                "app_canary_parent_invalid")
    info = CANARY.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o444 and info.st_size == len(CANARY_BYTES),
            "app_canary_identity_invalid")


def close_inherited_descriptors() -> None:
    # Landlock cannot revoke pre-opened FDs. A fresh worker receives no sockets
    # or secret file descriptors, even through stdin/stdout/stderr.
    for fd in (0, 1, 2):
        try:
            require(not stat.S_ISSOCK(os.fstat(fd).st_mode), "app_standard_fd_is_socket")
        except OSError as error:
            require(error.errno == errno.EBADF, "app_fd_inspection_failed")
    numbers = [int(p.name) for p in Path("/proc/self/fd").iterdir() if p.name.isdigit()]
    for fd in numbers:
        if fd > 2:
            try:
                os.close(fd)
            except OSError as error:
                require(error.errno == errno.EBADF, "app_fd_close_failed")


def _landlock(lib) -> int:
    abi = lib.syscall(C.c_long(NR_LANDLOCK_CREATE), C.c_void_p(), C.c_size_t(0), C.c_uint(1))
    require(abi >= MIN_LANDLOCK_ABI, "app_landlock_abi_unsupported")
    # TCP is additionally denied here; all protocols including UDP/Unix/raw are
    # covered by seccomp. Signal/abstract Unix scoping require ABI 6.
    rules = Ruleset(HANDLED_FS, 3, 3)
    descriptor = lib.syscall(C.c_long(NR_LANDLOCK_CREATE), C.byref(rules),
                             C.c_size_t(C.sizeof(rules)), C.c_uint(0))
    require(descriptor >= 0, "app_landlock_create_failed")
    try:
        entries = [(p, READ_EXEC_TREE) for p in READ_EXEC_PATHS]
        entries += [(p, READ_TREE) for p in READ_ONLY_PATHS]
        # Reading directory entries does not grant reading files in /data/private.
        entries += [("/data", FS_READ_DIR)]
        entries += [(p, WRITE_TREE) for p in WRITE_PATHS]
        entries += [(p, FS_READ | FS_WRITE) for p in DEVICE_FILES]
        for path, rights in entries:
            current = Path(path)
            info = current.lstat()
            require(not stat.S_ISLNK(info.st_mode), "app_policy_path_linked")
            if path in WRITE_PATHS:
                require(stat.S_ISDIR(info.st_mode), "app_policy_write_path_invalid")
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                rule = PathRule(rights, fd)
                require(lib.syscall(C.c_long(NR_LANDLOCK_ADD), C.c_int(descriptor),
                        C.c_int(1), C.byref(rule), C.c_uint(0)) == 0,
                        "app_landlock_rule_failed")
            finally:
                os.close(fd)
        require(lib.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0,
                "app_no_new_privileges_failed")
        require(lib.syscall(C.c_long(NR_LANDLOCK_RESTRICT), C.c_int(descriptor),
                           C.c_uint(0)) == 0, "app_landlock_enforcement_failed")
    finally:
        os.close(descriptor)
    return int(abi)


def filter_instructions() -> list[tuple[int, int, int, int]]:
    # BPF_LD|W|ABS=0x20, JMP|JEQ|K=0x15, JMP|JGE|K=0x35,
    # JMP|JSET|K=0x45, RET|K=0x06. seccomp_data: nr@0, arch@4, args[0]@16.
    kill, allow, denied = 0x80000000, 0x7FFF0000, 0x00050000 | errno.EPERM
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, kill),
            (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, kill)]
    for number in sorted(DENIED_SYSCALLS):
        rows += [(0x15, 0, 1, number), (0x06, 0, 0, denied)]
    # Process-resource changes must never target the API or an unrelated peer.
    for number in sorted(SELF_ONLY_SYSCALLS):
        rows += [(0x15, 0, 4, number), (0x20, 0, 0, 16),
                 (0x15, 1, 0, 0), (0x06, 0, 0, denied),
                 (0x06, 0, 0, allow)]
    # clone3 reports ENOSYS to permit glibc's normal clone fallback for threads.
    rows += [(0x15, 0, 1, 435), (0x06, 0, 0, 0x00050000 | errno.ENOSYS)]
    # Ordinary processes/threads are allowed; all new namespace flags are not.
    rows += [(0x15, 0, 3, 56), (0x20, 0, 0, 16),
             (0x45, 0, 1, CLONE_NAMESPACE_FLAGS), (0x06, 0, 0, denied),
             (0x06, 0, 0, allow)]
    return rows



# Supervisor starts apps without a Docker seccomp filter. Establish a private,
# inherited default-deny baseline instead of requiring operators to disable a
# protection check. The worker adds its stricter network/IPC/filesystem policy.
BASE_SYSCALL_NAMES = frozenset("""read write open openat close close_range stat fstat lstat newfstatat statx
poll ppoll select pselect6 lseek mmap mprotect munmap mremap madvise brk
rt_sigaction rt_sigprocmask rt_sigreturn rt_sigsuspend rt_sigpending rt_sigtimedwait
sigaltstack ioctl pread64 pwrite64 readv writev preadv pwritev preadv2 pwritev2
access faccessat faccessat2 pipe pipe2 dup dup2 dup3 fcntl flock fsync fdatasync
truncate ftruncate getdents getdents64 getcwd chdir fchdir rename renameat renameat2
mkdir mkdirat rmdir link linkat unlink unlinkat symlink symlinkat readlink readlinkat
umask chmod fchmod fchmodat fchmodat2 chown fchown lchown fchownat utime utimes utimensat futimesat
getxattr lgetxattr fgetxattr listxattr llistxattr flistxattr
sendfile copy_file_range splice tee vmsplice fallocate
socket socketpair connect accept accept4 bind listen shutdown
sendto recvfrom sendmsg recvmsg recvmmsg sendmmsg getsockname getpeername setsockopt getsockopt
fork vfork execve execveat wait4 waitid exit exit_group kill tgkill tkill
getpid getppid gettid getuid geteuid getgid getegid getgroups
setuid setgid setresuid setresgid setgroups getresuid getresgid
getpgid getpgrp setpgid setsid getsid capget
getrlimit setrlimit prlimit64 getrusage sysinfo uname times
sched_yield sched_getaffinity sched_setaffinity sched_getparam sched_getscheduler
sched_get_priority_max sched_get_priority_min sched_rr_get_interval
clock_gettime clock_getres clock_nanosleep nanosleep gettimeofday time
setitimer getitimer alarm timer_create timer_delete timer_settime timer_gettime timer_getoverrun
timerfd_create timerfd_settime timerfd_gettime eventfd eventfd2 signalfd signalfd4
epoll_create epoll_create1 epoll_ctl epoll_wait epoll_pwait epoll_pwait2
futex futex_waitv set_tid_address set_robust_list get_robust_list rseq restart_syscall
arch_prctl prctl getrandom memfd_create statfs fstatfs sync syncfs landlock_create_ruleset landlock_add_rule landlock_restrict_self""".split())

# Landlock intentionally does not mediate chmod, chown, timestamps or xattrs.
# Deny these for the worker, including their *at and newer syscall variants.
DENIED_SYSCALLS = DENIED_SYSCALLS | frozenset({
    90, 91, 92, 93, 94, 132, 133, 141, 188, 189, 190, 197, 198, 199,
    235, 259, 260, 261, 268, 280, 424, 440, 452,
})
SELF_ONLY_SYSCALLS = frozenset({142, 144, 203, 302})


def baseline_filter_instructions(resolve) -> list[tuple[int, int, int, int]]:
    """Generate a bounded amd64 default-deny policy; unknown calls stay denied."""
    require(resolve('clone') == 56 and resolve('clone3') == 435,
            'app_seccomp_architecture_mismatch')
    numbers = set()
    for name in BASE_SYSCALL_NAMES:
        number = resolve(name)
        require(type(number) is int, 'app_seccomp_resolution_invalid')
        if number >= 0:
            require(number < 0x40000000 and number not in {56, 435},
                    'app_seccomp_resolution_invalid')
            numbers.add(number)
    kill, allow, deny = 0x80000000, 0x7FFF0000, 0x50000 | errno.EPERM
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, kill),
            (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, kill)]
    for number in sorted(numbers):
        rows += [(0x15, 0, 1, number), (0x06, 0, 0, allow)]
    rows += [(0x15, 0, 1, 435), (0x06, 0, 0, 0x50000 | errno.ENOSYS),
             (0x15, 0, 4, 56), (0x20, 0, 0, 16),
             (0x45, 0, 1, CLONE_NAMESPACE_FLAGS), (0x06, 0, 0, deny),
             (0x06, 0, 0, allow), (0x06, 0, 0, deny)]
    require(len(rows) < 4096, 'app_seccomp_program_too_large')
    return rows


def install_process_baseline() -> dict:
    """Install before untrusted input; existing container filters are preserved."""
    lib = libc()
    before = kernel_status()
    require(before['threads'] == 1, 'app_baseline_already_multithreaded')
    sec = C.CDLL('libseccomp.so.2', use_errno=True)
    sec.seccomp_syscall_resolve_name.argtypes = [C.c_char_p]
    sec.seccomp_syscall_resolve_name.restype = C.c_int
    rows = baseline_filter_instructions(
        lambda name: int(sec.seccomp_syscall_resolve_name(name.encode('ascii'))))
    require(lib.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0,
            'app_no_new_privileges_failed')
    array = (Filter * len(rows))(*(Filter(*row) for row in rows))
    program = Program(len(rows), array)
    require(lib.prctl(PR_SET_SECCOMP, 2, C.byref(program), 0, 0) == 0,
            'app_baseline_enforcement_failed')
    after = kernel_status()
    require(after['seccomp'] == 2 and after['no_new_privileges'] == 1
            and after['seccomp_filters'] > before['seccomp_filters'],
            'app_baseline_not_observed')
    return {'default_deny_installed': True,
            'additional_filter_observed': True}


def _seccomp(lib) -> None:
    rows = filter_instructions()
    array = (Filter * len(rows))(*(Filter(*row) for row in rows))
    program = Program(len(rows), array)
    require(lib.prctl(PR_SET_SECCOMP, 2, C.byref(program), 0, 0) == 0,
            "app_seccomp_enforcement_failed")


def _denied_socket(family: int, kind: int) -> None:
    try:
        opened = socket.socket(family, kind)
    except OSError as error:
        require(error.errno == errno.EPERM, "app_socket_filter_not_observed")
    else:
        opened.close()
        raise PolicyError("app_socket_filter_missing")


def verify_applied() -> dict:
    """Check actual negative probes, not an environment variable or saved flag.

    The trusted launcher and integration tests establish the full rule set.
    These runtime observations are necessary but not an independent audit of
    every BPF instruction or every Landlock grant.
    """
    lib = libc()
    state = kernel_status()
    _require_base(state, single_threaded=False)
    require(state["no_new_privileges"] == 1 and state["seccomp_filters"] >= 2,
            "app_worker_kernel_protection_missing")
    _canary_identity()
    try:
        CANARY.read_bytes()
    except OSError as error:
        require(error.errno in (errno.EACCES, errno.EPERM), "app_canary_probe_invalid")
    else:
        raise PolicyError("app_filesystem_boundary_missing")
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            _denied_socket(family, kind)
    try:
        pair = socket.socketpair()
    except OSError as error:
        require(error.errno == errno.EPERM, "app_socketpair_filter_not_observed")
    else:
        for member in pair:
            member.close()
        raise PolicyError("app_socketpair_filter_missing")
    C.set_errno(0)
    result = lib.syscall(C.c_long(425), C.c_uint(0), C.c_void_p())
    require(result == -1 and C.get_errno() == errno.EPERM, "app_io_uring_filter_missing")
    return {"profile": PROFILE, "kernel_guards_observed": True,
            "engine_executed": False}


def apply() -> dict:
    lib = libc()
    _require_base(kernel_status(), single_threaded=True)
    _canary_identity()
    require(CANARY.read_bytes() == CANARY_BYTES, "app_canary_before_enforcement_invalid")
    close_inherited_descriptors()
    abi = _landlock(lib)
    _seccomp(lib)
    result = verify_applied()
    result["landlock_abi"] = abi
    return result


def seal_api_process() -> None:
    """Call before loading secrets; do not exec afterwards (exec resets it)."""
    lib = libc()
    require(lib.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) == 0
            and lib.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) == 0,
            "app_api_process_not_sealed")
