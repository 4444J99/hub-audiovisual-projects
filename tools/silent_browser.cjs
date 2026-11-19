/* Launch every Playwright browser through here so no run can make a sound. Chromium gets --mute-audio merged into
 * the caller's arguments, Firefox gets media.volume_scale=0.0 passed through firefox_user_prefs, and every context
 * (newContext, and newPage, which makes its own) gets silent-init.js: media elements pinned muted at volume 0 and a
 * gain-0 sink in front of every realtime AudioContext destination. The init script is engine-agnostic, so it is the
 * mute for the paths no flag or pref reaches. WebKit has no engine-level switch, so a page whose HTML carries a closed
 * declarative shadow root cannot be silenced there: silentLaunch refuses to set it. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const INIT_SCRIPT_PATH = path.join(__dirname, 'silent-init.js');
const MUTE_ARGS = ['--mute-audio'];
const FIREFOX_PREFS = {'media.volume_scale': 0.0};
// A closed declarative shadow root detaches its media from every page-side handle (host.shadowRoot is null and the
// parser never calls attachShadow), so no init script can pin it. Chromium and Firefox cover it with an engine-level
// switch; WebKit has none, so a page that contains one would play sound we cannot stop.
const CLOSED_DECLARATIVE_SHADOW_ROOT = /<template\b[^>]*?\bshadowrootmode\s*=\s*(?:"\s*closed\s*"|'\s*closed\s*'|closed\b)/i;
const REFUSAL = 'refusing to run a WebKit check page that contains a closed declarative shadow root '
  + '(<template shadowrootmode="closed">): its media cannot be silenced. Use an open shadow root, or run the check on Chromium or Firefox.';
const hasClosedDeclarativeShadowRoot = html => typeof html === 'string' && CLOSED_DECLARATIVE_SHADOW_ROOT.test(html);
const refuseClosedDeclarativeShadowRoot = html => { if (hasClosedDeclarativeShadowRoot(html)) throw new Error(REFUSAL); };
// Inline HTML in a data: URL can be scanned before it is set; anything served over HTTP is not scannable here.
function htmlFromDataUrl(url) {
  const match = /^data:([^,]+),([\s\S]*)$/.exec(url);
  if (!match) return null;
  const meta = match[1].toLowerCase();
  if (!/^text\/html(\s*;|$)/.test(meta)) return null;
  try {
    if (meta.includes('base64')) return Buffer.from(match[2], 'base64').toString('utf8');
    return decodeURIComponent(match[2]);
  } catch { return null; }
}
function wrapPage(page, engine) {
  if (!page || page.__silentRefusalWrapped || engine !== 'webkit') return page;
  page.__silentRefusalWrapped = true;
  if (typeof page.setContent === 'function') {
    const setContent = page.setContent.bind(page);
    page.setContent = async (html, ...rest) => { refuseClosedDeclarativeShadowRoot(html); return setContent(html, ...rest); };
  }
  if (typeof page.goto === 'function') {
    const navigate = page.goto.bind(page);
    page.goto = async (url, ...rest) => {
      const html = typeof url === 'string' ? htmlFromDataUrl(url) : null;
      if (html !== null) refuseClosedDeclarativeShadowRoot(html);
      return navigate(url, ...rest);
    };
  }
  return page;
}
const initScript = () => fs.readFileSync(INIT_SCRIPT_PATH, 'utf8');

const engineName = engine => (typeof engine.name === 'function' ? engine.name() : engine.name);

function silentArgs(name, args = []) {
  const merged = [...args];
  if (name === 'chromium') for (const flag of MUTE_ARGS) if (!merged.includes(flag)) merged.push(flag);
  return merged;
}

async function silenceContext(context, engine = null) {
  await context.addInitScript({path: INIT_SCRIPT_PATH});
  if (engine === 'webkit' && context && typeof context.newPage === 'function') {
    const newPage = context.newPage.bind(context);
    context.newPage = async (...args) => wrapPage(await newPage(...args), engine);
  }
  return context;
}

function engineNameOf(browser) {
  try { return typeof browser.browserType === 'function' ? engineName(browser.browserType()) : null; }
  catch { return null; }
}

function silenceBrowser(browser, name = null) {
  if (browser.__silentBrowser) return browser;
  const engine = name || engineNameOf(browser);
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async (...args) => silenceContext(await newContext(...args), engine);
  // Playwright's own newPage makes a context after the fact, so a script added to it would miss the blank document
  // that setContent and addScriptTag write into. Make the silenced context first, then the page, and close the
  // context with the page the way Playwright's owned context does.
  browser.newPage = async (...args) => {
    const context = await browser.newContext(...args), page = await context.newPage(), pageClose = page.close.bind(page);
    page.close = async (...closeArgs) => { try { await pageClose(...closeArgs); } finally { await context.close(); } };
    return page;
  };
  browser.__silentBrowser = true;
  return browser;
}

function firefoxPrefs(options) {
  // The pref is the mute, so it wins: a caller that passes media.volume_scale gets 0.0 anyway (the caller's other prefs are kept).
  return {...(options.firefoxUserPrefs || {}), ...FIREFOX_PREFS};
}

function withoutFirefoxPrefs(options) {
  const {firefoxUserPrefs, ...rest} = options;
  return rest;
}

async function silentLaunch(engine, options = {}) {
  const name = engineName(engine);
  const rest = withoutFirefoxPrefs(options);
  const launchOptions = {...rest, args: silentArgs(name, rest.args)};
  if (name === 'firefox') launchOptions.firefoxUserPrefs = firefoxPrefs(options);
  return silenceBrowser(await engine.launch(launchOptions), name);
}

// A persistent context is created with its first page already open, so that page's document is silenced by running
// the init script in it now; every later document and navigation gets it from the context.
async function silentLaunchPersistentContext(engine, userDataDir, options = {}) {
  const name = engineName(engine);
  const rest = withoutFirefoxPrefs(options);
  const launchOptions = {...rest, args: silentArgs(name, rest.args)};
  if (name === 'firefox') launchOptions.firefoxUserPrefs = firefoxPrefs(options);
  const context = await silenceContext(await engine.launchPersistentContext(userDataDir, launchOptions), name);
  for (const page of context.pages()) { wrapPage(page, name); await page.evaluate(initScript()); }
  return context;
}

module.exports = {INIT_SCRIPT_PATH, MUTE_ARGS, FIREFOX_PREFS, initScript, silentArgs, silenceContext, silenceBrowser, silentLaunch, silentLaunchPersistentContext, hasClosedDeclarativeShadowRoot, htmlFromDataUrl};
