/* Browser QA of this project's own local page; no user browser profile is used. */
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const ROOT = path.resolve(__dirname, '..');
const modulePath = process.env.PLAYWRIGHT_MODULE || require.resolve('playwright', {paths: [ROOT, path.resolve(ROOT, '../../Web/ridemate-web')]});
const {chromium} = require(modulePath);
const out = path.join(ROOT, 'target/uav-dashboard');

(async () => {
  const server = JSON.parse(fs.readFileSync(path.join(out, 'server.json'), 'utf8'));
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const errors = [];
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}, acceptDownloads: true});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(server.url);
    await page.locator('html[data-ready="true"]').waitFor();
    await page.locator('#stat-dqn').filter({hasText: '32,00 slot'}).waitFor();
    const readValue = async () => (await page.locator('#stat-dqn').innerText()).replace(/\s/g, '');
    assert.equal(await readValue(), '32,00slot');
    await page.selectOption('#checkpoint', 'final'); assert.equal(await readValue(), '23,46slot');
    await page.selectOption('#profile', 'REWARD_AFTER'); assert.equal(await readValue(), '31,47slot');
    await page.selectOption('#checkpoint', 'best'); assert.equal(await readValue(), '31,99slot');
    await page.selectOption('#profile', 'LOCAL_COMPLETION'); assert.equal(await readValue(), '12,17slot');
    await page.selectOption('#checkpoint', 'final'); assert.equal(await readValue(), '10,00slot');
    await page.selectOption('#profile', 'REFERENCE'); await page.selectOption('#checkpoint', 'best');
    const pointChecks = await page.evaluate(() => {
      const app = window.UAVDashboard, row = app.data.datasets[0].rows.find(r => r.profile === 'REFERENCE' && r.policy === 'DQN' && r.seed === 0 && r.checkpoint === 'best');
      const trace = app.data.datasets[0].traces[row.traceId];
      const a = app.pointAt(trace, 0), b = app.pointAt(trace, 10), c = app.pointAt(trace, 599), d = app.pointAt(trace, row.seconds);
      return {origin: Math.hypot(a.x, a.y),distance10: Math.hypot(b.x, b.y),hovering599: !c.moving,batteryEnd: d.battery};
    });
    assert.equal(pointChecks.origin, 0); assert.ok(Math.abs(pointChecks.distance10 - 50) < .001);
    assert.equal(pointChecks.hovering599, true); assert.equal(pointChecks.batteryEnd, 0);
    await page.selectOption('#seed', '1'); await page.selectOption('#task', '2000029');
    assert.ok((await page.locator('#map').innerText()).includes('Layout 0'));
    await page.locator('#rewind').click(); assert.ok((await page.locator('#time-label').innerText()).startsWith('0 /'));
    await page.locator('#play').click(); await page.waitForFunction(() => window.UAVDashboard.state.time > 0);
    await page.locator('#play').click(); assert.equal(await page.locator('#play').innerText(), 'Phát đường bay');
    await page.locator('#coverage').uncheck(); await page.selectOption('#focus', 'OLDEST_DATA');
    await page.locator('[data-policy="RANDOM"]').click(); assert.equal(await page.locator('[data-policy="RANDOM"]').getAttribute('aria-pressed'), 'false');
    await page.locator('[data-policy="RANDOM"]').click();
    const downloadPromise = page.waitForEvent('download'); await page.locator('#export').click();
    const download = await downloadPromise; await download.saveAs(path.join(out, 'export-test.csv'));
    assert.ok(fs.readFileSync(path.join(out, 'export-test.csv'), 'utf8').includes('REFERENCE'));
    await page.selectOption('#dataset', 'reference'); assert.equal(await readValue(), '21,00slot');
    await page.selectOption('#checkpoint', 'final'); assert.equal(await readValue(), '19,68slot');
    await page.selectOption('#seed', '2'); assert.ok((await page.locator('#map').innerText()).includes('Layout 2'));
    await page.selectOption('#dataset', 'mobile'); assert.equal(await readValue(), '19,78%');
    assert.equal(await page.locator('#checkpoint').isDisabled(), true);
    assert.equal(await page.locator('#task option').count(), 1);
    assert.ok((await page.locator('#map').innerText()).includes('Layout 42'));
    await page.selectOption('#metric', 'energy'); assert.equal(await readValue(), '62,82kJ');
    await page.selectOption('#dataset', 'conventions');
    for (const profile of ['REFERENCE','REWARD_AFTER','LOCAL_COMPLETION']) {
      await page.selectOption('#profile', profile);
      for (const cp of ['best','final']) {
        await page.selectOption('#checkpoint', cp);
        for (const metric of ['slots','seconds','energy']) {
          await page.selectOption('#metric', metric);
          assert.ok(!/NaN|undefined/.test(await page.locator('main').innerText()));
        }
      }
    }
    await page.selectOption('#profile', 'REFERENCE'); await page.selectOption('#checkpoint', 'best'); await page.selectOption('#metric', 'slots');
    await page.selectOption('#seed', '0'); await page.selectOption('#task', '2000000'); await page.selectOption('#focus', 'DQN');
    await page.locator('#coverage').check();
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    await page.screenshot({path: path.join(out, 'preview-desktop.png'), fullPage: true});
    await page.locator('#theme').click(); assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    await page.screenshot({path: path.join(out, 'preview-dark.png'), fullPage: true});
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    await page.setViewportSize({width: 520, height: 1000});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({path: path.join(out, 'preview-mobile.png'), fullPage: true});
    assert.deepEqual(errors, []);
    const result = {status:'PASS',page_errors:errors,checks:['means match audited CSVs','all profiles/best/final/metrics','paper/mobile separation','physical5m/s interpolation','playback/coverage/focus toggles','one-case trace availability','CSV export','dark/light','520px no horizontal overflow'],screenshots:['preview-desktop.png','preview-dark.png','preview-mobile.png']};
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify(result,null,2)); console.log(JSON.stringify(result,null,2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
