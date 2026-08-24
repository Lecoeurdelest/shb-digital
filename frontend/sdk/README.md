# @bank-digital/embed-sdk

Embeddable client for the BANK Digital headless agent core. The package has three programmatic
entry points:

- `@bank-digital/embed-sdk`: REST + fetch-SSE; no React or DOM import.
- `@bank-digital/embed-sdk/react`: compound React components plus `CustomerAssistant` and
  `RmCopilot` variants.
- `@bank-digital/embed-sdk/element`: Shadow DOM mount functions and custom-element registration.

React and element consumers must provide the `react` and `react-dom` 19+ peer dependencies. The
headless entry does not load those peers.

The browser artifact `dist/bank-digital-widget.iife.js` (also exported as the side-effect entry
`@bank-digital/embed-sdk/standalone.js`) auto-registers
`<bank-digital-customer-assistant>` and `<bank-digital-rm-copilot>`. In this repo's Docker/Nginx
image it is served at `/embed-sdk/dist/bank-digital-widget.iife.js`; it is not under `/assets`.
The runnable reference host is `/embed-sdk/examples/standalone.html` in that image.

This package intentionally has no approval/decision API. In this repository, see
[`docs/EMBED_SDK.md`](../../docs/EMBED_SDK.md) for the integration, auth, artifact-path, network and
data-boundary contract.
