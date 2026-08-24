export const bankDigitalStyles = `
:host, .bd-embed {
  --bd-accent: var(--bank-digital-accent, #d97757);
  --bd-surface: var(--bank-digital-surface, #ffffff);
  --bd-surface-soft: var(--bank-digital-surface-soft, #f6f3ef);
  --bd-text: var(--bank-digital-text, #1a1917);
  --bd-muted: var(--bank-digital-muted, #6d6861);
  --bd-border: var(--bank-digital-border, #ddd7cf);
  --bd-danger: var(--bank-digital-danger, #a33a32);
  --bd-font: var(--bank-digital-font, Inter, system-ui, sans-serif);
  color: var(--bd-text);
  font-family: var(--bd-font);
  box-sizing: border-box;
}
.bd-embed *, .bd-embed *::before, .bd-embed *::after { box-sizing: border-box; }
.bd-frame { position: relative; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; min-height: 360px; max-height: 720px; background: var(--bd-surface); border: 1px solid var(--bd-border); border-radius: 14px; overflow: hidden; }
.bd-frame--rm { grid-template-columns: minmax(280px, 1fr) minmax(260px, .85fr); grid-template-rows: auto auto minmax(0, 1fr) auto; }
.bd-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--bd-border); font-weight: 700; }
.bd-frame--rm .bd-header { grid-column: 1 / -1; }
.bd-disclaimer { grid-column: 1 / -1; padding: 7px 16px; color: var(--bd-muted); background: var(--bd-surface-soft); border-bottom: 1px solid var(--bd-border); font-size: 11px; line-height: 1.4; }
.bd-status { margin-left: auto; color: var(--bd-muted); font-size: 12px; font-weight: 500; }
.bd-status__dot { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 99px; background: var(--bd-muted); }
.bd-status__dot--open { background: #2f8f57; }
.bd-status__dot--connecting, .bd-status__dot--reconnecting { background: #c68518; }
.bd-messages { min-height: 0; overflow: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: var(--bd-surface-soft); }
.bd-message { max-width: 88%; padding: 9px 11px; border-radius: 12px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.45; font-size: 14px; }
.bd-message--user { align-self: flex-end; color: white; background: var(--bd-accent); }
.bd-message--assistant { align-self: flex-start; background: var(--bd-surface); border: 1px solid var(--bd-border); }
.bd-message--system { align-self: stretch; max-width: none; color: var(--bd-muted); background: transparent; text-align: center; font-size: 12px; }
.bd-stream-cursor::after { content: '▋'; color: var(--bd-accent); animation: bd-blink 1s steps(1) infinite; }
.bd-empty { margin: auto; color: var(--bd-muted); text-align: center; font-size: 13px; }
.bd-composer { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--bd-border); background: var(--bd-surface); }
.bd-frame--rm .bd-composer { grid-column: 1; }
.bd-composer input { min-width: 0; flex: 1; border: 1px solid var(--bd-border); border-radius: 10px; padding: 10px 12px; color: inherit; background: inherit; font: inherit; }
.bd-composer button { border: 0; border-radius: 10px; padding: 0 16px; color: white; background: var(--bd-accent); font: inherit; font-weight: 700; cursor: pointer; }
.bd-composer button:disabled, .bd-composer input:disabled { cursor: not-allowed; opacity: .55; }
.bd-cards { min-height: 0; overflow: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; border-left: 1px solid var(--bd-border); background: var(--bd-surface); }
.bd-card { border: 1px solid var(--bd-border); border-radius: 10px; padding: 12px; }
.bd-card__type { color: var(--bd-accent); font-size: 11px; font-weight: 700; text-transform: uppercase; }
.bd-card h3 { margin: 4px 0 8px; font-size: 14px; }
.bd-card time { display: block; margin: -3px 0 8px; color: var(--bd-muted); font-size: 10px; }
.bd-card ul { margin: 0; padding-left: 18px; }
.bd-card li { margin: 4px 0; font-size: 13px; overflow-wrap: anywhere; }
.bd-card__sources { margin-top: 8px; color: var(--bd-muted); font-size: 11px; }
.bd-error { position: absolute; z-index: 2; top: 48px; right: 8px; left: 8px; padding: 9px 10px; color: var(--bd-danger); background: var(--bd-surface); border: 1px solid color-mix(in srgb, var(--bd-danger) 35%, transparent); border-radius: 9px; box-shadow: 0 5px 18px rgba(0,0,0,.12); font-size: 12px; }
.bd-error button { float: right; border: 0; color: inherit; background: transparent; cursor: pointer; }
@keyframes bd-blink { 50% { opacity: 0; } }
@media (max-width: 720px) {
  .bd-frame--rm { grid-template-columns: 1fr; grid-template-rows: auto auto minmax(260px, 1fr) auto minmax(180px, .7fr); max-height: none; }
  .bd-frame--rm .bd-header, .bd-frame--rm .bd-disclaimer, .bd-frame--rm .bd-composer { grid-column: 1; }
  .bd-cards { border-left: 0; border-top: 1px solid var(--bd-border); }
}
`
