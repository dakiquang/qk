// qk for omp: a live status from `status-commands`, one reminder when a session starts, and /qk-brief to decide.
// Install: ln -s <qk>/adapters/omp/qk-status.ts ~/.omp/agent/extensions/qk-status.ts
// Tested with omp 19.0.0. `$QK_BIN` names the qk command (default `qk`).
const { execFile } = require('child_process')
const fs = require('fs')
const path = require('path')

const QK = process.env.QK_BIN || 'qk'
const REFRESH_MS = 15000

type Ui = {
  setStatus?: (key: string, text: string | undefined) => void
  notify?: (message: string, level: string) => void
  select?: (title: string, options: string[]) => Promise<string | undefined>
}

function run(command: string, args: string[], timeout: number): Promise<{ ok: boolean; out: string; err: string }> {
  return new Promise((resolve) => {
    execFile(command, args, { timeout }, (error, stdout, stderr) =>
      resolve({ ok: !error, out: String(stdout || '').trim(), err: String(stderr || '').trim() }))
  })
}

function qk(args: string[], timeout = 10000) {
  const words = QK.split(' ').filter(Boolean)
  return run(words[0], [...words.slice(1), ...args], timeout)
}

function statusScript(): string {
  try {
    return path.join(path.dirname(fs.realpathSync(__filename)), '..', 'status_lines.py')
  } catch {
    return ''
  }
}

function say(ui: Ui | null, message: string, level = 'info'): void {
  try {
    ui?.notify?.(message, level)
  } catch {}
}

async function decide(ui: Ui): Promise<void> {
  if (typeof ui.select !== 'function') {
    say(ui, 'qk: this omp has no select dialog; use the qk-morning skill instead', 'warning')
    return
  }
  const synced = await qk(['sync'], 60000)
  if (!synced.ok) say(ui, 'qk sync failed; PR states may be out of date: ' + synced.err.slice(-200), 'warning')
  const brief = await qk(['brief', '--json'])
  let cards: Array<{ run_id: string; lines: string[]; choices: string[]; decided: boolean }> = []
  try {
    cards = JSON.parse(brief.out).cards || []
  } catch {}
  if (cards.length === 0) {
    say(ui, brief.ok ? 'qk: nothing to decide' : 'qk brief failed: ' + brief.err.slice(-200))
    return
  }
  for (const card of cards) {
    const title = card.lines.join('\n') + (card.decided ? '\n(already decided; choose again to change it)' : '')
    const choice = await ui.select(title, [...card.choices, 'skip'])
    if (!choice || choice === 'skip') continue
    let result = await qk(['decide', card.run_id, choice], 120000)
    if (!result.ok && choice === 'merge' && result.err.includes('--method')) {
      const method = await ui.select('Merge method for ' + card.run_id, ['squash', 'merge', 'rebase', 'skip'])
      if (!method || method === 'skip') continue
      result = await qk(['decide', card.run_id, choice, '--method', method], 120000)
    }
    say(ui, result.ok ? result.out : 'qk decide: ' + result.err.slice(-300), result.ok ? 'info' : 'error')
  }
}

export default function (pi): void {
  let ui: Ui | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let shown = ''

  async function refresh(): Promise<void> {
    const script = statusScript()
    const result = script ? await run('python3', [script], 3000) : { ok: false, out: '', err: '' }
    const text = result.ok ? result.out.split('\n').filter(Boolean).join(' | ') : ''
    if (text === shown) return
    shown = text
    try {
      ui?.setStatus?.('qk', text || undefined)
    } catch {}
  }

  pi.on('session_start', async (_event, ctx) => {
    ui = ctx?.ui ?? null
    if (!timer) {
      timer = setInterval(() => void refresh(), REFRESH_MS)
      timer.unref?.()
    }
    void refresh()
    const pending = await qk(['brief', '--pending'], 5000)
    if (pending.ok && pending.out) say(ui, pending.out + ' (or /qk-brief here)')
  })
  pi.on('agent_end', () => void refresh())
  pi.on('session_shutdown', () => {
    if (timer) clearInterval(timer)
    timer = null
    ui = null
    shown = ''
  })
  if (typeof pi.registerCommand === 'function') {
    pi.registerCommand('qk-brief', {
      description: 'Read the qk brief cards and record your decisions',
      handler: async (_args, ctx) => decide(ctx.ui),
    })
  }
}
