// Real Edge + WebHID, read-only integration check. No mocked device APIs.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
fs.mkdirSync(path.join(root, 'reports'), { recursive: true });
fs.mkdirSync(path.join(root, 'backups'), { recursive: true });
const temporary = path.join(root, '.runtime', 'qa-temp');
fs.mkdirSync(temporary, { recursive: true });
process.env.TEMP = temporary;
process.env.TMP = temporary;

(async () => {
  const interactive = process.argv.includes('--interactive');
  const replay = process.argv.includes('--replay');
  const context = interactive
    ? await chromium.launchPersistentContext(path.join(root, '.runtime', 'browser-profile'), {
      channel: 'msedge', headless: false, locale: 'zh-CN', viewport: { width: 1440, height: 1000 },
    })
    : await (await chromium.launch({ channel: 'msedge', headless: true })).newContext({
      locale: 'zh-CN', viewport: { width: 1440, height: 1000 },
    });
  const browser = context.browser();
  if (replay) {
    const backupFile = fs.readdirSync(path.join(root, 'backups')).filter(n => /^rx980-\d.*\.json$/.test(n)).sort().at(-1);
    const backup = JSON.parse(fs.readFileSync(path.join(root, 'backups', backupFile), 'utf8'));
    await context.addInitScript(data => {
      const bytes = hex => Uint8Array.from(hex.match(/../g).map(x => parseInt(x, 16)));
      const replies = new Map(data.traffic.map(row => [row.request.slice(0, 14), row.reply]));
      let last = new Uint8Array(64);
      const readOnly = new Set([0x8f, 0x80, 0x85, 0x86, 0x87, 0x89, 0x8a, 0x8b, 0x8c, 0x90, 0x91, 0x92, 0x97, 0xad, 0xae]);
      const device = {
        vendorId: 0x3151, productId: 0x4010, productName: 'RX980 Gaiming Keyboard', opened: false,
        collections: [{ usagePage: 65535, usage: 2, children: [], inputReports: [], outputReports: [],
          featureReports: [{ reportId: 0, items: [{ reportSize: 8, reportCount: 64 }] }] }],
        async open() { this.opened = true; }, async close() { this.opened = false; },
        addEventListener() {}, removeEventListener() {},
        async sendFeatureReport(id, raw) {
          const packet = new Uint8Array(raw);
          if (id !== 0 || !readOnly.has(packet[0])) throw new Error('Replay rejects all writes');
          const key = Array.from(packet.slice(0, 7)).map(b => b.toString(16).padStart(2, '0')).join('');
          const response = replies.get(key);
          if (response) last = bytes(response);
        },
        async receiveFeatureReport() { return new DataView(last.slice().buffer); },
      };
      Object.defineProperty(navigator, 'hid', { value: {
        async getDevices() { return [device]; }, async requestDevice() { return [device]; },
        addEventListener() {}, removeEventListener() {},
      } });
    }, backup);
  }
  const page = context.pages()[0] || await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('framenavigated', f => { if (f === page.mainFrame()) console.log('Navigation:', f.url()); });
  const cdp = await context.newCDPSession(page);
  await cdp.send('DeviceAccess.enable');
  cdp.on('DeviceAccess.deviceRequestPrompted', async event => {
    console.log('HID chooser:', event.devices.map(d => d.name));
    const chosen = event.devices.find(d => /^RX980 /i.test(d.name));
    if (chosen) await cdp.send('DeviceAccess.selectPrompt', { id: event.id, deviceId: chosen.id });
  });
  try {
    await page.goto('http://127.0.0.1:19806', { waitUntil: 'networkidle' });
    if (!interactive && !replay) await page.getByRole('button', { name: '连接键盘', exact: true }).click({ timeout: 15000 });
    else if (interactive) console.log('Waiting for RX980 in the browser, reusing any existing device permission.');
    let ready = false;
    for (let attempt = 0; attempt < (interactive ? 240 : 20); attempt++) {
      ready = await page.evaluate(async () => {
        try { return Number.isInteger(await window.sharkfin.getProfile()); }
        catch { return false; }
      });
      if (ready) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    if (!ready) throw new Error('The browser did not connect to the wired RX980');
    const scan = await page.evaluate(() => window.sharkfin.scan());
    console.log('Scan result:', JSON.stringify(scan));
    const settings = await page.evaluate(() => window.sharkfin.getSettings());
    const led = await page.evaluate(() => window.sharkfin.getLedParam());
    await page.getByRole('button', { name: '按键', exact: true }).click();
    await page.waitForTimeout(1500);
    const suffix = replay ? '-replay' : '';
    await page.screenshot({ path: path.join(root, 'reports/rx980-keys' + suffix + '.png'), fullPage: true });
    await page.getByRole('button', { name: '设备', exact: true }).click();
    await page.waitForTimeout(1000);
    const autoControl = await page.getByText('自动识别电脑系统', { exact: true }).count();
    await page.screenshot({ path: path.join(root, 'reports/rx980-device' + suffix + '.png'), fullPage: true });
    if (scan.connected.readOnly || scan.connected.spec.family !== 'yc500' || autoControl !== 0) {
      throw new Error('RX980 capabilities did not match the hardware evidence');
    }
    const downloadEvent = page.waitForEvent('download');
    await page.evaluate(() => window.sharkfin.exportConfig('rx980-sharkfin-backup.json'));
    const download = await downloadEvent;
    await download.saveAs(path.join(root, 'backups/rx980-sharkfin-backup' + suffix + '.json'));
    const report = { actualWebHid: !replay, replay, scan, settings, led, unsupportedAutoOsHidden: autoControl === 0, errors };
    fs.writeFileSync(path.join(root, 'reports/ui-smoke' + suffix + '.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ deviceId: scan.connected.deviceId, family: scan.connected.spec.family,
      readOnly: scan.connected.readOnly, layout: scan.connected.spec.keyLayout, settings, errors }, null, 2));
    if (errors.length) throw new Error('Browser reported application errors');
  } catch (e) {
    console.error('UI state:', await page.locator('body').innerText());
    console.error('Errors:', errors);
    await page.screenshot({ path: path.join(root, 'reports/ui-error.png'), fullPage: true });
    throw e;
  } finally {
    if (interactive) await context.close();
    else await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
