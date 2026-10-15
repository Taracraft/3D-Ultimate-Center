export const DIRECT_PRINT_PANEL_STYLES = `
  ultimate-3d-direct-print-panel{display:block;width:100%;max-width:100%;min-width:0;color:#eef5ff;font:13px/1.45 Inter,Segoe UI,sans-serif}
  *{box-sizing:border-box}
  .dp-root,.dp-panel{display:block;width:100%;max-width:100%;min-width:0}
  .dp-panel{position:relative;overflow:hidden;border:1px solid #29455d;border-radius:16px;background:linear-gradient(180deg,#101d29 0%,#0a141e 100%);box-shadow:0 18px 44px #0006}
  .dp-panel::before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#32c8ff,#5cdd7b,#f0c65b)}
  .dp-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:18px 18px 15px;border-bottom:1px solid #22384a;background:linear-gradient(180deg,#132333,#0f1d29)}
  .dp-title{min-width:0}
  .dp-kicker{display:block;margin-bottom:4px;color:#67c9f3;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
  .dp-title h3{margin:0;font-size:20px;line-height:1.2}
  .dp-title p{max-width:720px;margin:6px 0 0;color:#91a6ba}
  .dp-head-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;justify-content:flex-end}
  .dp-mode{display:inline-flex;align-items:center;gap:7px;min-height:32px;padding:6px 10px;border:1px solid #34644a;border-radius:999px;background:#10291d;color:#8ff0aa;font-size:11px;font-weight:800;white-space:nowrap}
  .dp-mode::before{content:"";width:8px;height:8px;border-radius:50%;background:#61df80;box-shadow:0 0 12px #61df80}
  .dp-body{padding:16px 18px 18px}
  .dp-progress{height:9px;overflow:hidden;background:#203245}
  .dp-progress span{display:block;width:38%;height:100%;background:linear-gradient(90deg,#00beff,#00ffb1);animation:dp-slide 1.05s ease-in-out infinite}
  .dp-printer-grid{display:grid;grid-template-columns:minmax(260px,1.25fr) minmax(220px,.75fr);gap:12px}
  .dp-field{display:grid;gap:6px}
  .dp-field>span{color:#8da4b8;font-size:11px;font-weight:700}
  .dp-select,.dp-input{width:100%;min-height:48px;border:1px solid #31506e;border-radius:11px;background:#07121d;color:#fff;padding:10px 12px;font-size:14px}
  .dp-select:focus,.dp-input:focus{outline:2px solid #42c8ff;outline-offset:1px}
  .dp-ready-card{display:flex;align-items:center;gap:11px;min-height:48px;padding:10px 12px;border:1px solid #28734d;border-radius:11px;background:#10271b}
  .dp-ready-card.blocked{border-color:#8d4650;background:#35191f}
  .dp-ready-dot{flex:none;width:12px;height:12px;border-radius:50%;background:#5ee07b;box-shadow:0 0 13px #5ee07b}
  .dp-ready-card.blocked .dp-ready-dot{background:#e36976;box-shadow:0 0 13px #e36976}
  .dp-ready-copy{min-width:0}
  .dp-ready-copy strong,.dp-ready-copy span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .dp-ready-copy span{margin-top:2px;color:#9cb1c3;font-size:11px}
  .dp-section{margin-top:16px}
  .dp-section-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
  .dp-section-head h4{margin:0;font-size:14px}
  .dp-section-head span{color:#8399ad;font-size:11px}
  .dp-slot-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:10px}
  .dp-slot{display:grid;gap:9px;width:100%;padding:12px;border:1px solid #2c4255;border-radius:12px;background:#0b1721;color:#eef5ff;text-align:left;cursor:pointer;transition:transform .14s ease,border-color .14s ease,background .14s ease,box-shadow .14s ease}
  .dp-slot:hover:not(:disabled){transform:translateY(-1px);border-color:#4b7898;background:#0e1d29}
  .dp-slot.selected{border-color:#56d978;background:#10271a;box-shadow:inset 0 0 0 1px #56d97855,0 0 22px #42d66a18}
  .dp-slot:disabled{opacity:.5;cursor:not-allowed}
  .dp-slot-top{display:grid;grid-template-columns:32px minmax(0,1fr) auto;gap:9px;align-items:center}
  .dp-color{width:30px;height:30px;border:1px solid #ffffff55;border-radius:50%;background:var(--slot-color);box-shadow:0 0 0 3px #ffffff0b}
  .dp-slot-name{min-width:0}
  .dp-slot-name strong,.dp-slot-name span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .dp-slot-name span{color:#8da2b5;font-size:10px}
  .dp-slot-state{padding:4px 7px;border-radius:999px;background:#203447;color:#a9bed0;font-size:10px;font-weight:800}
  .dp-slot.selected .dp-slot-state{background:#245e39;color:#a4f5b8}
  .dp-slot-data{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 10px;padding-top:8px;border-top:1px solid #233748}
  .dp-slot-data span{display:grid;gap:1px;color:#8096aa;font-size:9px;text-transform:uppercase;letter-spacing:.04em}
  .dp-slot-data b{overflow:hidden;text-overflow:ellipsis;color:#eff6fc;font-size:11px;text-transform:none;letter-spacing:0;white-space:nowrap}
  .dp-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:9px}
  .dp-check{display:flex;align-items:center;gap:10px;min-height:52px;padding:11px 12px;border:1px solid #283d51;border-radius:11px;background:#0a151f;cursor:pointer;touch-action:manipulation}
  .dp-check:hover{border-color:#3c5f7a;background:#0d1b27}
  .dp-check input{flex:none;width:21px;height:21px;accent-color:#64d86b}
  .dp-check-copy strong,.dp-check-copy span{display:block}
  .dp-check-copy span{margin-top:2px;color:#8298ab;font-size:10px}
  .dp-prepared,.dp-warning,.dp-error,.dp-success,.dp-empty{margin-top:12px;padding:12px 13px;border-radius:11px;overflow-wrap:anywhere}
  .dp-prepared{display:grid;gap:5px;border:1px solid #3475a0;background:#102538}
  .dp-warning{border:1px solid #855b28;background:#332413;color:#ffd69c}
  .dp-error{border:1px solid #8d4650;background:#35191f;color:#ffc0c8}
  .dp-success{border:1px solid #28734d;background:#10271b;color:#b6f3c3}
  .dp-empty{border:1px dashed #365168;background:#0b1721;color:#93a8bb;text-align:center}
  .dp-mono{font:10px ui-monospace,Consolas,monospace;overflow-wrap:anywhere}
  .dp-actions{display:flex;align-items:center;justify-content:flex-end;gap:9px;flex-wrap:wrap;margin-top:15px;padding-top:14px;border-top:1px solid #22384a}
  .dp-action-note{margin-right:auto;max-width:560px;color:#8ba0b3;font-size:11px}
  .dp-button{min-height:44px;border:1px solid #31506e;border-radius:10px;background:#14263a;color:#eef5ff;padding:10px 14px;cursor:pointer;font-weight:800;font-size:13px;touch-action:manipulation}
  .dp-button:hover:not(:disabled){border-color:#4ac6ff;background:#17324a}
  .dp-button:focus{outline:2px solid #42c8ff;outline-offset:2px}
  .dp-button:disabled{opacity:.38;cursor:not-allowed}
  .dp-primary{min-width:210px;border-color:#4fd56f;background:linear-gradient(180deg,#63df7c,#48c966);color:#06200d;box-shadow:0 8px 22px #39c85c22}
  .dp-primary:hover:not(:disabled){border-color:#77ed8e;background:linear-gradient(180deg,#77e98d,#58d976)}
  .dp-danger{border-color:#7c3d48;background:#421d25;color:#ffc4ca}
  .dp-retry{border-color:#d48639;background:#4c2b13;color:#ffd4a6}
  .dp-result{display:grid;gap:4px}
  ultimate-3d-direct-print-panel[compact]{font-size:11px;line-height:1.25}
  ultimate-3d-direct-print-panel[compact] .dp-panel{border-radius:6px;box-shadow:none}
  ultimate-3d-direct-print-panel[compact] .dp-head{align-items:center;gap:8px;padding:7px 9px}
  ultimate-3d-direct-print-panel[compact] .dp-kicker{margin-bottom:1px;font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-title h3{font-size:13px}
  ultimate-3d-direct-print-panel[compact] .dp-title p{display:none}
  ultimate-3d-direct-print-panel[compact] .dp-head-actions{gap:5px}
  ultimate-3d-direct-print-panel[compact] .dp-mode{min-height:24px;padding:3px 6px;font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-button{min-height:30px;padding:5px 8px;border-radius:5px;font-size:10px}
  ultimate-3d-direct-print-panel[compact] .dp-body{padding:7px 9px 8px}
  ultimate-3d-direct-print-panel[compact] .dp-progress{height:4px}
  ultimate-3d-direct-print-panel[compact] .dp-printer-grid{grid-template-columns:minmax(220px,1fr) minmax(170px,230px);gap:6px}
  ultimate-3d-direct-print-panel[compact] .dp-field{gap:2px}
  ultimate-3d-direct-print-panel[compact] .dp-field>span{font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-select{min-height:31px;padding:5px 7px;border-radius:5px;font-size:10px}
  ultimate-3d-direct-print-panel[compact] .dp-ready-card{min-height:31px;padding:5px 7px;border-radius:5px;gap:6px}
  ultimate-3d-direct-print-panel[compact] .dp-ready-dot{width:8px;height:8px}
  ultimate-3d-direct-print-panel[compact] .dp-ready-copy strong{font-size:9px}
  ultimate-3d-direct-print-panel[compact] .dp-ready-copy span{font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-section{margin-top:6px}
  ultimate-3d-direct-print-panel[compact] .dp-section-head{margin-bottom:4px}
  ultimate-3d-direct-print-panel[compact] .dp-section-head h4{font-size:10px}
  ultimate-3d-direct-print-panel[compact] .dp-section-head span{font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-options{grid-template-columns:repeat(5,minmax(125px,1fr));gap:4px}
  ultimate-3d-direct-print-panel[compact] .dp-check{min-height:34px;padding:5px 6px;border-radius:5px;gap:5px}
  ultimate-3d-direct-print-panel[compact] .dp-check input{width:14px;height:14px}
  ultimate-3d-direct-print-panel[compact] .dp-check-copy strong{font-size:9px}
  ultimate-3d-direct-print-panel[compact] .dp-check-copy span{display:none}
  ultimate-3d-direct-print-panel[compact] .dp-actions{margin-top:6px;padding-top:6px;gap:5px}
  ultimate-3d-direct-print-panel[compact] .dp-action-note{font-size:8px}
  ultimate-3d-direct-print-panel[compact] .dp-primary{min-width:135px}
  ultimate-3d-direct-print-panel[compact] .dp-prepared,
  ultimate-3d-direct-print-panel[compact] .dp-warning,
  ultimate-3d-direct-print-panel[compact] .dp-error,
  ultimate-3d-direct-print-panel[compact] .dp-success,
  ultimate-3d-direct-print-panel[compact] .dp-empty{margin-top:5px;padding:5px 7px;border-radius:5px;font-size:9px}
  @keyframes dp-slide{0%{transform:translateX(-110%)}50%{transform:translateX(120%)}100%{transform:translateX(280%)}}
  @media(max-width:1100px){ultimate-3d-direct-print-panel[compact] .dp-options{grid-template-columns:repeat(3,minmax(125px,1fr))}}
  @media(max-width:760px){
    .dp-panel{border-radius:12px}.dp-head{padding:14px;align-items:stretch;flex-direction:column}.dp-head-actions{justify-content:space-between}.dp-body{padding:12px}.dp-printer-grid{grid-template-columns:1fr}.dp-slot-grid{grid-template-columns:1fr}.dp-options{grid-template-columns:1fr}.dp-actions{display:grid;grid-template-columns:1fr}.dp-action-note{margin:0 0 4px}.dp-button{width:100%;min-height:50px;font-size:14px}.dp-primary{min-width:0}.dp-slot-data{grid-template-columns:repeat(3,minmax(0,1fr))}
    ultimate-3d-direct-print-panel[compact] .dp-printer-grid,ultimate-3d-direct-print-panel[compact] .dp-options{grid-template-columns:1fr}
  }
  @media(max-width:430px){.dp-slot-data{grid-template-columns:repeat(2,minmax(0,1fr))}.dp-title h3{font-size:18px}.dp-head-actions{align-items:stretch;flex-direction:column}.dp-mode{justify-content:center}}
`;
