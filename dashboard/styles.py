from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    /* Every text token clears WCAG AA (>=4.5:1) on the white card, and every severity label
       clears it on its own tint. Ratios vs the card: ink 10.4, muted 6.0, faint 5.3. The page
       canvas sits a full step below the card (1.20:1) so containers read as raised surfaces,
       and border tokens are strong enough to bound a card without looking like a wireframe.
       Severity stays red/amber/blue for critical/moderate/minor; the tints carry the at-a-glance
       signal while the text label (never colour alone) carries identity. */
    :root { --navy:#102b3f; --ink:#334c5e; --muted:#5d7381; --faint:#718591; --line:#b9cbd0; --line-soft:#d8e4e2; --surface:#ffffff; --surface-tint:#f8fbfa; --page:#e8f0ee; --sidebar:#edf5f0; --blue:#2d647d; --blue-bg:#e5f1f5; --blue-line:#b5d2dc; --amber:#a56a14; --amber-bg:#fff3d9; --amber-line:#e7c887; --red:#a52e2b; --red-bg:#fff0ee; --red-line:#e4b5b1; --green:#338451; --green-bg:#e6f4e9; --green-line:#b9d9c0; --focus:#2d647d; --sidebar-text:#213d4b; --card-border:#1b2b35; --checklist-text:#214957; }
    .stApp { background:var(--page); color:var(--ink); font-family:'DM Sans',sans-serif; }
    [data-testid="stAppViewContainer"] > .main { background:linear-gradient(135deg,#e8f0ee 0%,#edf3f5 55%,#f6f3eb 100%); }
    .main .block-container { max-width:1440px; }
    .stApp p, .stApp label, .stApp .stMarkdown, .stApp [data-testid="stCaptionContainer"] { color:var(--ink); }
    [data-testid="stSidebar"] { background:var(--sidebar); border-right:1px solid var(--line); color:var(--sidebar-text); }
    [data-testid="stSidebar"] > div:first-child { padding-top:0!important; }
    [data-testid="stAppViewContainer"] .main .block-container,[data-testid="stMainBlockContainer"] { padding-top:1.5rem!important; }
     /* Streamlit renders st.navigation before user content regardless of call order. Reorder
         the sidebar regions so the brand and site selector lead the page links visually. */
    [data-testid="stSidebarContent"] { display:flex!important; flex-direction:column!important; }
     [data-testid="stSidebarUserContent"] { order:1!important; }
    [data-testid="stSidebarUserContent"] { padding-bottom:.35rem!important; margin-bottom:0!important; }
    [data-testid="stSidebarNav"] { order:2!important; margin-top:0!important; padding-top:0!important; }
    [data-testid="stSidebar"] * { color:var(--sidebar-text)!important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p, [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] [data-testid="stSidebarNav"] a { color:var(--sidebar-text)!important; }
    [data-testid="stSidebarNav"] { display:block; } [data-testid="stSidebarNav"] ul { margin-top:0!important; padding-top:.25rem!important; } [data-testid="stSidebarNav"] a { color:var(--navy)!important; font-weight:600; border-radius:8px; } [data-testid="stSidebarNav"] a[aria-current="page"] { background:#ffffff!important; box-shadow:0 2px 5px rgba(27,55,65,.1); } [data-testid="stHeader"],[data-testid="stAppHeader"] { background:transparent; } [data-testid="stToolbar"] { visibility:hidden; }
    /* Keep the sidebar collapse/expand affordance permanently visible — Streamlit only reveals
       it on hover by default, which reads as a missing control on a wall-mounted display. */
    [data-testid="stSidebarCollapseButton"],[data-testid="stExpandSidebarButton"] { display:flex!important; visibility:visible!important; opacity:1!important; }
    [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] { top:.75rem!important; left:.75rem!important; }
    [data-testid="stSidebarCollapseButton"] button,[data-testid="stExpandSidebarButton"] button { width:2rem!important; height:2rem!important; padding:0!important; background:var(--surface)!important; border:1px solid var(--line)!important; border-radius:8px!important; color:var(--muted)!important; box-shadow:0 1px 2px rgba(16,27,45,.06)!important; } [data-testid="stSidebarCollapseButton"] button:hover,[data-testid="stExpandSidebarButton"] button:hover { color:var(--navy)!important; border-color:#8fa2b6!important; background:#f7fafc!important; }
    h1,h2,h3,h4,p,span,label,div { font-family:'DM Sans',sans-serif; } h1 { font-size:1.75rem!important; font-weight:600!important; letter-spacing:-.015em; color:var(--navy)!important; } h2 { font-size:1.05rem!important; font-weight:600!important; letter-spacing:-.005em; color:var(--navy)!important; } h3 { font-size:1rem!important; font-weight:600!important; color:var(--navy)!important; }
    /* Cards are real Streamlit containers (st.container(border=True)) so their border actually
       encloses their contents. Section heads and rows sit flush to the container's own padding. */
    [data-testid="stVerticalBlockBorderWrapper"] { background:var(--surface)!important; border:1.5px solid #263842!important; border-radius:10px; box-shadow:0 4px 12px rgba(27,55,65,.08); }
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { background:var(--surface)!important; border:1.5px solid #263842!important; border-radius:10px; box-shadow:0 4px 12px rgba(27,55,65,.08); }
    [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stMetric"]) { border-color:#000!important; }
    /* The metric card provides its own frame, so the inner metric widget carries none. */
    [data-testid="stMetric"] { background:transparent; border:0; padding:0; }
    [data-testid="stMetricLabel"] { color:var(--muted)!important; } [data-testid="stMetricLabel"] p { font-size:.72rem!important; font-weight:600!important; letter-spacing:.06em; text-transform:uppercase; color:var(--muted)!important; }
    [data-testid="stMetricValue"] { color:var(--navy)!important; font-size:2rem!important; font-weight:600!important; line-height:1.15!important; letter-spacing:-.02em; }
    [data-testid="stMetricDelta"] { display:none!important; }
    [data-testid="stMetric"]:after { content:""; position:absolute; right:-.8rem; bottom:-1.35rem; width:5rem; height:5rem; border:.8rem solid #e4f0e8; border-radius:50%; }
    .metric-caption { color:var(--faint); font-size:.75rem; margin-top:.3rem; line-height:1.4; }
    [data-testid="stMetric"] { position:relative; overflow:hidden; } [data-testid="stMetric"] > div { position:relative; z-index:1; }
    .brand-wordmark { color:var(--navy)!important; font-family:'DM Sans',sans-serif!important; font-size:1.1rem; font-weight:600; line-height:1.2; } .st-key-sidebar-brand,.st-key-mobile-brand { padding:0 0 .35rem; } .st-key-mobile-brand { display:none; } .st-key-sidebar-brand [data-testid="stHorizontalBlock"],.st-key-mobile-brand [data-testid="stHorizontalBlock"] { align-items:center!important; } .st-key-sidebar-brand [data-testid="stImage"] img,.st-key-mobile-brand [data-testid="stImage"] img { width:60px; height:60px; object-fit:cover; border-radius:0; border:0!important; background:transparent; }
    /* Active Site uses Streamlit's current React-Aria combobox markup, not BaseWeb select markup. */
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"] { background:var(--blue)!important; border:0!important; color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; caret-color:#ffffff!important; font-family:'DM Sans',sans-serif!important; }
    [data-testid="stSidebar"] div:has(> input[aria-label="Active site"][role="combobox"]) { background:var(--blue)!important; border:1px solid var(--blue)!important; box-shadow:none!important; }
    [data-testid="stSidebar"] div:has(input[aria-label="Active site"][role="combobox"]) button { background:#ffffff!important; border:1px solid var(--blue)!important; color:var(--navy)!important; }
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"]:focus,
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"]:focus-visible { outline:none!important; border:0!important; box-shadow:none!important; }
    [data-testid="stSidebar"] div:has(> input[aria-label="Active site"][role="combobox"]):focus-within { border-color:var(--blue)!important; outline:0!important; box-shadow:0 0 0 1px var(--blue)!important; }
    [data-testid="stSidebar"] [role="listbox"] [role="option"] { background:var(--navy)!important; color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; }
    [data-testid="stSidebar"] .sidebar-status { position:fixed; left:1.25rem; bottom:1.25rem; color:var(--muted)!important; font-family:'DM Sans',sans-serif!important; font-size:.78rem; line-height:1.8; }
    .eyebrow { color:var(--faint); font-size:.7rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; } .page-intro { color:var(--muted); font-size:.92rem; margin-top:-.5rem; margin-bottom:1.75rem; } .page-shell { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1.4rem; } .breadcrumb { color:var(--faint); font-family:'IBM Plex Mono',monospace; font-size:.72rem; } .breadcrumb strong { color:var(--navy); font-weight:600; } .live-status { display:flex; align-items:center; gap:.45rem; color:#2f7d4a; font-size:.76rem; font-weight:600; white-space:nowrap; } .live-dot { width:.45rem; height:.45rem; border-radius:50%; background:#3d9a5b; } .live-status.offline { color:var(--amber); } .live-status.offline .live-dot { background:#c7892f; }
    .section-gap { height:1.75rem; }
    .section-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.1rem 0 .85rem; border-bottom:1px solid var(--line-soft); margin-bottom:.35rem; } .section-head h2 { margin:0; } .section-head p { color:var(--faint); margin:.25rem 0 0; font-size:.8rem; }
    .count { background:var(--line-soft); color:var(--navy); padding:.2rem .55rem; border-radius:999px; font-family:'IBM Plex Mono',monospace; font-size:.76rem; }
    .badge,.status-badge { display:inline-block; border:1px solid; border-radius:4px; padding:.16rem .45rem; font-size:.7rem; font-weight:600; letter-spacing:.01em; white-space:nowrap; } .status-badge { border-radius:999px; }
    .sev-critical { color:var(--red); background:var(--red-bg); border-color:var(--red-line); } .sev-moderate { color:var(--amber); background:var(--amber-bg); border-color:var(--amber-line); } .sev-minor { color:var(--blue); background:var(--blue-bg); border-color:var(--blue-line); } .sev-none { color:var(--navy); background:var(--line-soft); border-color:var(--line); }
    .status-active { color:var(--red); background:var(--red-bg); border-color:var(--red-line); } .status-acknowledged { color:var(--amber); background:var(--amber-bg); border-color:var(--amber-line); } .status-resolved { color:var(--blue); background:var(--blue-bg); border-color:var(--blue-line); }
    .alert-row { margin:.55rem 0; padding:.85rem .9rem .7rem; background:var(--surface-tint); border:1.5px solid var(--card-border); border-radius:8px; box-shadow:0 4px 10px rgba(27,55,65,.08); } .alert-row:last-child { margin-bottom:.25rem; } .alert-row.critical { background:var(--red-bg); box-shadow:inset 4px 0 0 var(--red), 0 4px 10px rgba(165,46,43,.1); padding-left:1rem; } .alert-row.moderate { background:var(--amber-bg); box-shadow:inset 4px 0 0 var(--amber), 0 4px 10px rgba(165,106,20,.1); padding-left:1rem; } .alert-row.minor { background:var(--blue-bg); box-shadow:inset 4px 0 0 var(--blue), 0 4px 10px rgba(45,100,125,.1); padding-left:1rem; } .alert-title { display:flex; align-items:center; flex-wrap:wrap; gap:.5rem; font-size:.95rem; font-weight:600; color:var(--navy); } .alert-meta { color:var(--faint); font-size:.74rem; letter-spacing:.01em; margin:.4rem 0 .5rem; } .alert-row .muted { color:var(--ink); font-size:.86rem; line-height:1.5; }
    .compliance-label { display:flex; justify-content:space-between; gap:1rem; margin:.75rem 0 .15rem; color:var(--muted); font-size:.76rem; } .compliance-label strong { color:var(--navy); } .compliance-bar { height:.55rem; margin:.2rem 0 .15rem; overflow:hidden; display:flex; background:#cbd9d3; border-radius:999px; } .compliance-fill { height:100%; background:var(--green); } .compliance-legend { display:flex; justify-content:space-between; color:var(--faint); font-size:.66rem; }
    [class*="st-key-alert-actions-"] { margin-top:.7rem; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] details { border:0!important; border-radius:6px!important; box-shadow:none!important; background:transparent!important; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] summary { min-height:2.25rem; padding:.45rem .7rem!important; border:1px solid var(--line)!important; border-radius:6px!important; background:#f7fafc!important; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] summary:hover { border-color:#8fa2b6!important; background:#eef3f7!important; } [class*="st-key-alert-actions-"] button { min-height:2.25rem!important; width:100%!important; }
    /* Labelled detail fields replace the previous raw JSON dump. */
    .detail-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr)); gap:.6rem 1.25rem; padding:.7rem 0 .2rem; } .detail-grid .detail-value { font-size:.84rem; } .detail-label { color:var(--faint); font-size:.68rem; font-weight:600; letter-spacing:.07em; text-transform:uppercase; } .detail-value { color:var(--ink); font-size:.88rem; margin-top:.15rem; line-height:1.45; } .detail-note { color:var(--faint); font-size:.75rem; font-style:italic; margin-top:.5rem; } .detail-ref { color:var(--faint); font-family:'IBM Plex Mono',monospace; font-size:.7rem; margin-top:.85rem; }
    /* Reference images: fixed width + square crops => identical heights, so they line up.
       Captions are suppressed outright; the label sits above the image instead. */
    .reference-label { margin:.9rem 0 .35rem; }
    [data-testid="stImage"] { margin:0; } [data-testid="stImage"] img { border-radius:8px; border:1px solid var(--line-soft); display:block; }
    [data-testid="stImageCaption"], [data-testid="stImage"] figcaption { display:none!important; }
    .muted { color:var(--muted); } .empty { text-align:center; padding:2.75rem 1.25rem; color:var(--ink); font-size:.88rem; } .chart-empty { min-height:10rem; display:flex; align-items:center; justify-content:center; box-sizing:border-box; background:#f5f8f7; border-radius:7px; } .mono { font-family:'IBM Plex Mono',monospace; font-size:.84rem; color:var(--ink); } .mobile-brand { display:none; } .sidebar-workspace { color:var(--faint)!important; font-size:.68rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; margin:.55rem 0 .2rem; } .sidebar-status { border-top:1px solid var(--line-soft); padding-top:.75rem; }
    button { border-radius:6px!important; background:#fff!important; color:var(--ink)!important; border:1px solid var(--line)!important; font-weight:500!important; } button p { color:inherit!important; font-size:.84rem!important; } button:hover:not(:disabled) { border-color:#8fa2b6!important; background:#f7fafc!important; color:var(--navy)!important; }
    button[kind="primary"] { background:var(--navy)!important; color:#fff!important; border-color:var(--navy)!important; } button[kind="primary"]:hover { background:#1c2c44!important; } button[kind="primary"] p { color:#fff!important; }
    button:disabled, button[disabled] { background:var(--page)!important; color:var(--muted)!important; border-color:var(--line)!important; box-shadow:none!important; cursor:not-allowed!important; }
    /* Keyboard usability: Streamlit ships no visible focus ring on these controls. */
    button:focus-visible, summary:focus-visible, input:focus-visible, select:focus-visible, [role="checkbox"]:focus-visible, textarea:focus-visible { outline:2px solid var(--focus)!important; outline-offset:2px!important; }
    /* Form controls need a border strong enough to find on a bright site display. */
    [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] { border-color:var(--line)!important; background:var(--surface)!important; } [data-baseweb="select"] > div:hover, [data-baseweb="input"]:hover { border-color:#8fa2b6!important; }
    [data-testid="stWidgetLabel"] p { color:var(--muted)!important; font-size:.76rem!important; font-weight:600!important; }
    [data-testid="stExpander"] details { border:1.5px solid var(--card-border)!important; border-radius:8px!important; background:var(--surface)!important; box-shadow:0 1px 3px rgba(16,27,45,.08); }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { font-size:.88rem!important; color:var(--navy)!important; -webkit-text-fill-color:var(--navy)!important; }
    [data-testid="stExpander"] details[open] > summary, [data-testid="stExpander"] details[open] > summary * { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; background:#101b2d!important; }
    [data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:hover * { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; background:#101b2d!important; }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"], [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p, [data-testid="stExpander"] .detail-value, [data-testid="stExpander"] .mono { color:var(--ink)!important; }
    [data-testid="stExpander"] .detail-label, [data-testid="stExpander"] .detail-note, [data-testid="stExpander"] .detail-ref { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] p, [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] li { color:var(--ink); }
    [data-testid="stVerticalBlockBorderWrapper"] .section-head p, [data-testid="stVerticalBlockBorderWrapper"] .metric-caption { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .detail-label { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .detail-value { color:var(--ink)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .badge, [data-testid="stVerticalBlockBorderWrapper"] .status-badge { color:inherit; }
    [data-testid="stCheckbox"] label { color:var(--checklist-text)!important; font-weight:600; }
    [data-testid="stCheckbox"] span { color:var(--checklist-text)!important; }
    [data-testid="stCheckbox"] .stCheckbox { border-left:2px solid var(--blue-line); padding-left:.35rem; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] p { color:var(--muted)!important; }
    .response-note { margin-top:.8rem; padding:.7rem .8rem; border-left:2px solid #4a9a61; background:#f1f7f2; color:var(--ink); line-height:1.45; } .response-empty { margin-top:.8rem; padding:1rem .75rem; background:#f7fafc; }
    .protocol-icon { display:inline-grid; place-items:center; width:2rem; height:2rem; margin-right:.55rem; border-radius:7px; background:var(--green-bg); color:var(--green); font-family:'IBM Plex Mono',monospace; font-size:.75rem; font-weight:600; vertical-align:middle; } .protocol-description { color:var(--muted); font-size:.8rem; margin:.3rem 0 .8rem 2.55rem; } .protocol-footer { display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--line-soft); margin-top:.8rem; padding-top:.65rem; }
    .library-banner { margin-top:1rem; padding:.75rem; background:#f5f0e3; color:#7a5410; font-size:.76rem; line-height:1.45; border-radius:6px; } .library-legend { margin-top:.8rem; color:var(--muted); font-size:.76rem; line-height:2; } .legend-dot { display:inline-block; width:.45rem; height:.45rem; margin-right:.35rem; border-radius:50%; } .legend-critical { background:var(--red); } .legend-moderate { background:#c7892f; } .legend-recorded { background:#3d9a5b; }
     /* The pinned base theme is light, so the dialog must explicitly provide its own light
         surface and dark form text instead of relying on Streamlit's overlay defaults. */
     [data-testid="stDialog"] [role="dialog"] { background:var(--surface)!important; color:var(--ink)!important; border:1.5px solid var(--card-border)!important; box-shadow:0 18px 45px rgba(16,43,63,.2)!important; }
     [data-testid="stDialog"] [role="dialog"] * { color:var(--ink)!important; }
     [data-testid="stDialog"] [role="dialog"] h1, [data-testid="stDialog"] [role="dialog"] h2, [data-testid="stDialog"] [role="dialog"] h3, [data-testid="stDialog"] [role="dialog"] h4, [data-testid="stDialog"] [role="dialog"] .dialog-incident-title { color:var(--navy)!important; }
     [data-testid="stDialog"] [role="dialog"] .dialog-incident-title { font-weight:700; letter-spacing:-.01em; }
     [data-testid="stDialog"] [role="dialog"] .dialog-incident-meta { color:var(--muted)!important; font-size:.86rem; }
     [data-testid="stDialog"] [role="dialog"] [data-testid="stCaptionContainer"] p, [data-testid="stDialog"] [role="dialog"] [data-testid="stCheckbox"] label, [data-testid="stDialog"] [role="dialog"] [data-testid="stCheckbox"] span { color:var(--ink)!important; }
     [data-testid="stDialog"] [role="dialog"] [data-testid="stWidgetLabel"] p { color:var(--muted)!important; }
     [data-testid="stDialog"] [role="dialog"] input[type="checkbox"] { accent-color:var(--green); }
     [data-testid="stDialog"] [role="dialog"] textarea { color:var(--ink)!important; background:var(--surface)!important; border:1.5px solid var(--line)!important; }
     [data-testid="stDialog"] [role="dialog"] textarea::placeholder { color:var(--faint)!important; opacity:1!important; }
     [data-testid="stDialog"] [role="dialog"] button { color:var(--ink)!important; border-color:var(--line)!important; background:var(--surface)!important; }
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"], [data-testid="stDialog"] [role="dialog"] [data-testid="stBaseButton-primary"] { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; background:var(--blue)!important; border-color:var(--blue)!important; }
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"] p, [data-testid="stDialog"] [role="dialog"] [data-testid="stBaseButton-primary"] p { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; }
    @media (max-width:800px) { .st-key-mobile-brand { display:block; } .page-intro { margin-bottom:1rem; } .section-gap { height:1rem; } }
    </style>
    """,
        unsafe_allow_html=True,
    )
