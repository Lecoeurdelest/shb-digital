import { execFileSync } from 'node:child_process'
import {
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = resolve(scriptDir, '../..')
const sdkDir = resolve(frontendDir, 'sdk')
const tempDir = mkdtempSync(join(tmpdir(), 'bank-digital-sdk-smoke-'))
const packDir = join(tempDir, 'pack')
const consumerDir = join(tempDir, 'consumer')

function run(command, args, cwd = frontendDir) {
  return execFileSync(command, args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
}

function readJavaScriptTree(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const path = join(directory, entry.name)
      if (entry.isDirectory()) return readJavaScriptTree(path)
      return entry.name.endsWith('.js') ? [readFileSync(path, 'utf8')] : []
    })
    .join('\n')
}

try {
  mkdirSync(packDir)
  mkdirSync(consumerDir)
  const packed = JSON.parse(
    run('npm', ['pack', sdkDir, '--pack-destination', packDir, '--json']),
  )
  const tarball = join(packDir, packed[0].filename)
  const entries = run('tar', ['-tf', tarball]).trim().split('\n')
  if (!entries.includes('package/dist/index.js') || !entries.includes('package/dist/types/index.d.ts')) {
    throw new Error('Tarball thiếu headless JS hoặc declarations')
  }
  if (entries.some((entry) => entry.includes('/src/') || entry.includes('.test.'))) {
    throw new Error('Tarball làm lộ source/test ngoài artifact phát hành')
  }
  const allowedArtifact = (entry) =>
    entry === 'package/package.json' ||
    entry === 'package/README.md' ||
    entry === 'package/dist/.vite/license.md' ||
    /^package\/dist\/(?:[^/]+\.(?:js|cjs|md)|types\/.+\.d\.ts)$/.test(entry)
  const unexpected = entries.filter((entry) => !allowedArtifact(entry))
  if (unexpected.length) {
    throw new Error(`Tarball chứa file ngoài SDK allowlist: ${unexpected.join(', ')}`)
  }
  const packedBytes = statSync(tarball).size
  if (packedBytes > 350_000) {
    throw new Error(`Tarball vượt size gate 350KB: ${packedBytes} bytes`)
  }

  writeFileSync(
    join(consumerDir, 'package.json'),
    JSON.stringify({ name: 'embed-sdk-consumer-smoke', private: true, type: 'module' }, null, 2),
  )
  run(
    'npm',
    ['install', tarball, '--ignore-scripts', '--no-package-lock', '--legacy-peer-deps'],
    consumerDir,
  )
  // Headless entry phải chạy khi consumer chưa hề cài/symlink React peer dependencies.
  run(
    process.execPath,
    ['--input-type=module', '-e', "import('@bank-digital/embed-sdk').then(m=>{if(!m.createBankDigitalClient)process.exit(2)})"],
    consumerDir,
  )
  run(
    process.execPath,
    ['-e', "const m=require('@bank-digital/embed-sdk');if(!m.createBankDigitalClient)process.exit(2)"],
    consumerDir,
  )
  for (const dependency of ['react', 'react-dom']) {
    symlinkSync(
      resolve(frontendDir, 'node_modules', dependency),
      resolve(consumerDir, 'node_modules', dependency),
      'dir',
    )
  }
  mkdirSync(resolve(consumerDir, 'node_modules/@types'))
  for (const dependency of ['react', 'react-dom', 'node']) {
    symlinkSync(
      resolve(frontendDir, 'node_modules/@types', dependency),
      resolve(consumerDir, 'node_modules/@types', dependency),
      'dir',
    )
  }
  mkdirSync(join(consumerDir, 'src'))
  writeFileSync(
    join(consumerDir, 'src/main.tsx'),
    `import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBankDigitalClient } from '@bank-digital/embed-sdk'
import { RmCopilot } from '@bank-digital/embed-sdk/react'
import { defineBankDigitalElements } from '@bank-digital/embed-sdk/element'

const client = createBankDigitalClient({ apiBaseUrl: '' })
defineBankDigitalElements()
createRoot(document.getElementById('root')!).render(
  <RmCopilot client={client} conversationId="consumer-smoke" />,
)
`,
  )
  writeFileSync(
    join(consumerDir, 'index.html'),
    '<!doctype html><html><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>',
  )
  writeFileSync(
    join(consumerDir, 'standalone.html'),
    '<!doctype html><html><body><script type="module" src="/src/standalone.ts"></script></body></html>',
  )
  writeFileSync(
    join(consumerDir, 'vite.standalone.config.mjs'),
    `import { resolve } from 'node:path'

export default {
  build: {
    outDir: 'dist-standalone',
    rolldownOptions: { input: resolve(import.meta.dirname, 'standalone.html') },
  },
}
`,
  )
  writeFileSync(
    join(consumerDir, 'src/cjs.cts'),
    `const { createBankDigitalClient } = require('@bank-digital/embed-sdk')
const client = createBankDigitalClient({ apiBaseUrl: '' })
void client.me()
`,
  )
  writeFileSync(
    join(consumerDir, 'src/standalone.ts'),
    "import '@bank-digital/embed-sdk/standalone.js'\n",
  )
  writeFileSync(
    join(consumerDir, 'tsconfig.json'),
    JSON.stringify(
      {
        compilerOptions: {
          target: 'ES2022',
          lib: ['ES2022', 'DOM'],
          module: 'ESNext',
          moduleResolution: 'Bundler',
          jsx: 'react-jsx',
          strict: true,
          noEmit: true,
          skipLibCheck: true,
        },
        include: ['src/main.tsx', 'src/standalone.ts'],
      },
      null,
      2,
    ),
  )

  run(resolve(frontendDir, 'node_modules/.bin/tsc'), ['-p', 'tsconfig.json'], consumerDir)
  writeFileSync(
    join(consumerDir, 'tsconfig.cjs.json'),
    JSON.stringify(
      {
        compilerOptions: {
          target: 'ES2022',
          lib: ['ES2022', 'DOM'],
          module: 'NodeNext',
          moduleResolution: 'NodeNext',
          strict: true,
          noEmit: true,
          skipLibCheck: true,
          types: ['node'],
        },
        include: ['src/cjs.cts'],
      },
      null,
      2,
    ),
  )
  run(resolve(frontendDir, 'node_modules/.bin/tsc'), ['-p', 'tsconfig.cjs.json'], consumerDir)
  run(resolve(frontendDir, 'node_modules/.bin/vite'), ['build'], consumerDir)
  run(
    resolve(frontendDir, 'node_modules/.bin/vite'),
    ['build', '--config', 'vite.standalone.config.mjs'],
    consumerDir,
  )
  const standaloneConsumerBundle = readJavaScriptTree(join(consumerDir, 'dist-standalone'))
  if (
    !standaloneConsumerBundle.includes('bank-digital-customer-assistant') ||
    !standaloneConsumerBundle.includes('bank-digital-rm-copilot')
  ) {
    throw new Error('Vite đã loại side-effect đăng ký custom elements khỏi standalone import')
  }
  const installedStandalonePath = join(
    consumerDir,
    'node_modules/@bank-digital/embed-sdk/dist/bank-digital-widget.iife.js',
  )
  const standalone = readFileSync(installedStandalonePath, 'utf8')
  if (Buffer.byteLength(standalone) > 260_000) {
    throw new Error(`Standalone vượt size gate 260KB: ${Buffer.byteLength(standalone)} bytes`)
  }
  if (!standalone.includes('bank-digital-rm-copilot')) {
    throw new Error('Standalone bundle không đăng ký RM custom element')
  }
  const browser = new JSDOM('<!doctype html><html><body></body></html>', {
    runScripts: 'outside-only',
    url: 'https://host.bank.example/',
  })
  browser.window.eval(standalone)
  if (
    !browser.window.customElements.get('bank-digital-customer-assistant') ||
    !browser.window.customElements.get('bank-digital-rm-copilot')
  ) {
    throw new Error('Packed standalone không register đủ custom elements trong browser')
  }
  browser.window.close()
  process.stdout.write(
    `SDK consumer smoke PASS: ${entries.length} files/${packedBytes} bytes; ESM+CJS+types+Vite+Vite-standalone+browser-standalone\n`,
  )
} finally {
  rmSync(tempDir, { recursive: true, force: true })
}
