// Optional rendered-directory check using an existing Playwright installation.
const {chromium}=require(process.env.OSRI_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),output=path.join(root,'research','qa');
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const options={headless:true};if(process.env.OSRI_CHROMIUM)options.executablePath=process.env.OSRI_CHROMIUM;
  const browser=await chromium.launch(options),page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('file://'+path.join(root,'index.html'));
  const data=await page.evaluate(()=>catalog);
  assert(data.venues.every(v=>v.ai_policy?.compatibility==='compatible'&&['research','analysis_code','manuscript_drafting'].every(k=>['allowed','conditional'].includes(v.ai_policy.permissions?.[k]))));
  assert(data.venues.every(v=>v.submission_status!=='closed'&&v.submission_status!=='paused'&&v.route.eligibility!=='not_free'));
  const recommended=v=>v.route.eligibility==='verified_free'&&v.route.submission_fee==='none'&&v.route.publication_fee==='none'&&v.review.type==='peer_reviewed'&&v.quality?.status!=='concerns';
  const expected=data.venues.filter(recommended).length;assert.equal(await page.locator('.venue').count(),expected);assert.match(await page.locator('#counts').textContent(),new RegExp(String(data.summary.verified_free_peer_reviewed_open_for_consideration)));assert.doesNotMatch(await page.locator('#counts').textContent(),/undefined/);const freePeerCount=data.venues.filter(v=>v.route.eligibility==='verified_free'&&v.route.submission_fee==='none'&&v.route.publication_fee==='none'&&v.review.type==='peer_reviewed').length;assert.match(await page.locator('#counts').textContent(),new RegExp(`${freePeerCount} verified free peer-reviewed routes`));assert.match(await page.locator('#counts').textContent(),new RegExp(`${expected} default recommendations after quality review`));if(data.summary.verified_free_peer_reviewed_before_quality!==undefined)assert.equal(data.summary.verified_free_peer_reviewed_before_quality,freePeerCount);
  assert.equal(await page.locator('#sort option[value="difficulty"]').count(),0);
  assert(data.venues.every(v=>['supported','needs_verification','concerns'].includes(v.quality?.status)));
  assert.equal(await page.locator('#quality').inputValue(),'no_concerns');
  for(const status of ['supported','needs_verification','concerns','']){await page.selectOption('#quality',status);assert.equal(await page.locator('.venue').count(),data.venues.filter(v=>v.route.eligibility==='verified_free'&&v.route.submission_fee==='none'&&v.route.publication_fee==='none'&&v.review.type==='peer_reviewed'&&(!status||v.quality.status===status)).length,status);}
  await page.click('#reset-filters');assert.equal(await page.locator('#quality').inputValue(),'no_concerns');assert.equal(await page.locator('.venue').count(),expected);
  if(expected){const first=page.locator('.venue').first();assert.match(await first.textContent(),/Submission cost[\s\S]*Publication cost[\s\S]*Reported metrics/);assert.match(await first.textContent(),/AI use and disclosure/);await first.locator('summary').click();assert(await first.getByRole('heading',{name:'Fee evidence'}).isVisible());const firstData=data.venues.find(v=>recommended(v));if(firstData.source_files?.length)assert.equal(await first.locator('.detail a').filter({hasText:firstData.source_files[0]}).getAttribute('href'),firstData.source_files[0]);}
  for(const f of data.subfields){await page.selectOption('#subfield',f.id);assert.equal(await page.locator('.venue').count(),data.venues.filter(v=>recommended(v)&&(v.subfields||[]).includes(f.id)).length,f.id);}
  await page.click('#reset-filters');await page.selectOption('#eligibility','');await page.selectOption('#quality','');await page.uncheck('#peer');assert.equal(await page.locator('.venue').count(),data.venues.length);
  const indexed=data.venues.find(v=>(v.quality.indexing||[]).some(i=>i.registry_url));if(indexed){await page.fill('#query',indexed.name);const card=page.locator('.venue').filter({has:page.getByRole('heading',{name:indexed.name,exact:true})});await card.locator('summary').click();for(const entry of indexed.quality.indexing.filter(i=>i.registry_url))assert(await card.locator('a').evaluateAll((as,url)=>as.some(a=>a.getAttribute('href')===url),entry.registry_url));await page.fill('#query','');}
  for(const basis of ['venue','publisher']){
    await page.selectOption('#location-basis',basis);
    const key=basis==='venue'?'venue_countries':'publisher_countries';
    const country=data.venues.flatMap(v=>v.geography?.[key]||[])[0];
    if(country){await page.selectOption('#country',country.code);assert.equal(await page.locator('.venue').count(),data.venues.filter(v=>(v.geography?.[key]||[]).some(c=>c.code===country.code)).length,basis+' country');await page.selectOption('#country','');}
    const regionOptions=await page.locator('#region option').evaluateAll(os=>os.map(o=>o.value).filter(Boolean));
    if(regionOptions.length){await page.selectOption('#region',regionOptions[0]);const expectedRegion=await page.evaluate(r=>catalog.venues.filter(v=>regions(v).includes(r)).length,regionOptions[0]);assert.equal(await page.locator('.venue').count(),expectedRegion,basis+' region');await page.selectOption('#region','');}
  }
  await page.click('#reset-filters');await page.fill('#query','no-such-venue-000000');assert(await page.getByRole('heading',{name:'No venues match these filters'}).isVisible());await page.click('#reset-filters');
  for(const sort of ['acceptance','jif','citescore']){await page.selectOption('#sort',sort);assert.match(await page.locator('#sort-note').textContent(),/reported/i);}
  await page.screenshot({path:path.join(output,'desktop.png'),fullPage:false});await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');await page.screenshot({path:path.join(output,'mobile.png'),fullPage:false});assert.deepEqual(errors,[]);
  const digest=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
  const report={status:'pass',default_results:expected,total_venues:data.venues.length,subfields_checked:data.subfields.length,catalog_sha256:digest('data/venues.json'),html_sha256:digest('index.html'),checks:['AI compatibility gate','cost, review and quality default', 'quality filters and reset', 'index evidence links','venue geography filter','subfield filters','disclosure and metric display','metric sorts','empty state and reset','desktop and mobile','browser errors']};
  fs.writeFileSync(path.join(output,'browser-check.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
