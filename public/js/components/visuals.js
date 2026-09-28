// Decorative inline-SVG illustrations. Purely abstract — no numbers, no fake
// thumbnails, no data. Colours come from CSS classes bound to tokens.

/** Concentric "platter" with recovered arcs, explicit gaps and a read arm. */
export function platter({ className = "", label = "" } = {}) {
  const a11y = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true" focusable="false"';
  return `<svg class="platter ${className}" viewBox="0 0 400 400" ${a11y}>
    <defs>
      <radialGradient id="platter-glow" cx="50%" cy="50%" r="50%"><stop offset="0%" class="pg-a"/><stop offset="100%" class="pg-b"/></radialGradient>
      <linearGradient id="platter-disc" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" class="pd-a"/><stop offset="100%" class="pd-b"/></linearGradient>
    </defs>
    <circle cx="200" cy="200" r="198" fill="url(#platter-glow)"/>
    <g class="platter__rings">
      <circle cx="200" cy="200" r="188"/><circle cx="200" cy="200" r="158"/><circle cx="200" cy="200" r="128"/><circle cx="200" cy="200" r="98"/>
    </g>
    <g class="platter__spin">
      <circle class="arc arc--amber" cx="200" cy="200" r="158" pathLength="1000" stroke-dasharray="120 880" stroke-dashoffset="40"/>
      <circle class="arc arc--green" cx="200" cy="200" r="158" pathLength="1000" stroke-dasharray="70 930" stroke-dashoffset="-260"/>
      <circle class="arc arc--gap" cx="200" cy="200" r="158" pathLength="1000" stroke-dasharray="40 960" stroke-dashoffset="-180"/>
      <circle class="arc arc--yellow" cx="200" cy="200" r="128" pathLength="1000" stroke-dasharray="90 910" stroke-dashoffset="-520"/>
      <circle class="arc arc--amber" cx="200" cy="200" r="128" pathLength="1000" stroke-dasharray="150 850" stroke-dashoffset="-120"/>
      <circle class="arc arc--gap" cx="200" cy="200" r="128" pathLength="1000" stroke-dasharray="36 964" stroke-dashoffset="-640"/>
      <circle class="arc arc--green" cx="200" cy="200" r="188" pathLength="1000" stroke-dasharray="54 946" stroke-dashoffset="-700"/>
      <circle class="arc arc--amber" cx="200" cy="200" r="98" pathLength="1000" stroke-dasharray="200 800" stroke-dashoffset="-360"/>
    </g>
    <circle class="platter__disc" cx="200" cy="200" r="66" fill="url(#platter-disc)"/>
    <circle class="platter__hub-ring" cx="200" cy="200" r="24"/>
    <circle class="platter__hub" cx="200" cy="200" r="7"/>
    <g class="platter__arm">
      <line x1="318" y1="74" x2="238" y2="166"/>
      <circle cx="318" cy="74" r="9"/>
      <circle class="platter__head" cx="238" cy="166" r="4.5"/>
    </g>
  </svg>`;
}
