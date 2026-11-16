// Use an existing Playwright installation. Screenshots go outside the checkout.
const {chromium}=require(process.env.OSRI_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const root=path.resolve(__dirname,'..');
(async()=>{
 const output=process.env.OSRI_QA_OUTPUT;assert(output,'Set OSRI_QA_OUTPUT to an external screenshot directory');fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.OSRI_CHROMIUM?{executablePath:process.env.OSRI_CHROMIUM}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const url=process.env.OSRI_DIRECTORY_URL||'file://'+path.join(root,'index.html');await page.goto(url);
 assert.match(await page.title(),/publication/i);assert(await page.getByRole('heading',{name:'Find a free publication route.'}).isVisible());
 const data=await page.locator('#venue-catalog').evaluate(el=>JSON.parse(el.textContent));
 const ids=()=>page.locator('.venue').evaluateAll(xs=>xs.map(x=>x.dataset.id));
 assert.deepEqual(await ids(),data.views.documented);assert.equal(await page.locator('#view').inputValue(),'documented');
 for(const v of data.venues)assert(v.ai_policy.compatibility==='compatible');
 for(const view of ['documented','incomplete','all']){await page.selectOption('#view',view);assert.deepEqual(await ids(),data.views[view]);}
 await page.click('#reset-filters');
 for(const f of data.subfields){await page.selectOption('#subfield',f.id);assert.equal(await page.locator('.venue').count(),data.venues.filter(v=>data.views.documented.includes(v.id)&&v.subfields.includes(f.id)).length);}
 await page.click('#reset-filters');
 const choices=(await ids()).slice(0,4);
 for(const id of choices.slice(0,3))await page.locator(`[data-select="${id}"]`).check();
 await page.locator(`[data-select="${choices[3]}"]`).click();assert.equal(await page.locator(`[data-select="${choices[3]}"]`).isChecked(),false);assert.match(await page.locator('#selection-notice').textContent(),/up to three/);
 await page.click('#show-comparison');assert(await page.getByRole('table').isVisible());assert.equal(await page.locator('#comparison thead th').count(),4);assert.match(await page.locator('#comparison').textContent(),/Submission cost[\s\S]*Publication cost[\s\S]*AI use and disclosure/);
 const bookmark=page.url();await page.reload();assert.equal(await page.locator('[data-select]:checked').count(),3);assert.equal(page.url(),bookmark);
 await page.selectOption('#subfield',data.subfields[0].id);assert.equal(await page.locator('#comparison thead th').count(),4);await page.click('#reset-filters');assert.equal(await page.locator('[data-select]:checked').count(),3);
 await page.click('#show-comparison');await page.locator('[data-remove]').first().click();assert.equal(await page.locator('#comparison thead th').count(),3);
 await page.click('#clear-shortlist');assert(await page.locator('#comparison').isHidden());
 await page.selectOption('#view','all');await page.locator('#more-filters>summary').click();await page.selectOption('#quality','concerns');
 const flagged=data.venues.filter(v=>v.quality.status==='concerns');assert.equal(await page.locator('.venue').count(),flagged.length);assert(await page.locator('.warning').first().isVisible());
 if(flagged.length){await page.locator('[data-select]').first().check();await page.click('#show-comparison');assert.match(await page.locator('#comparison').textContent(),new RegExp(flagged[0].quality.concerns[0].summary.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));await page.click('#clear-shortlist');}
 await page.selectOption('#quality','');await page.selectOption('#country','US');const countryIds=await ids();assert(countryIds.every(id=>data.venues.find(v=>v.id===id).geography.venue_countries.some(c=>c.code==='US')));
 await page.selectOption('#location-basis','publisher');assert.equal(await page.locator('#country').inputValue(),'');await page.selectOption('#country','GB');assert((await ids()).every(id=>data.venues.find(v=>v.id===id).geography.publisher_countries.some(c=>c.code==='GB')));
 await page.click('#reset-filters');await page.fill('#query','missing-venue-000000');assert(await page.getByRole('heading',{name:'No venues match these filters'}).isVisible());await page.click('#reset-filters');
 const first=page.locator('.venue').first();await first.locator('[data-panel="costs"]>summary').click();await first.getByRole('heading',{name:'Fee evidence',exact:true}).waitFor({state:'visible'});await first.locator('[data-panel="ai"]>summary').click();await first.locator('[data-panel="ai"]').getByRole('heading',{name:/^Disclosure/}).waitFor({state:'visible'});await first.locator('[data-panel="quality"]>summary').click();await first.getByRole('heading',{name:'Peer review',exact:true}).waitFor({state:'visible'});await first.locator('[data-panel="sources"]>summary').click();await first.getByRole('heading',{name:'Research provenance'}).waitFor({state:'visible'});
 for(const sort of ['acceptance','jif','citescore']){await page.selectOption('#sort',sort);assert.match(await page.locator('#sort-note').textContent(),/reported/i);}
 await page.click('#reset-filters');const u=new URL(page.url());u.search='compare=does-not-exist';await page.goto(u.href);assert.match(await page.locator('#selection-notice').textContent(),/unavailable/);
 await page.selectOption('#view','all');await page.selectOption('#view','incomplete');await page.goBack();assert.equal(await page.locator('#view').inputValue(),'all');await page.goForward();assert.equal(await page.locator('#view').inputValue(),'incomplete');await page.click('#reset-filters');
 for(const [name,width,height] of [['desktop',1440,1100],['tablet',768,1024],['mobile',390,844]]){
  await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' overflow');await page.screenshot({path:path.join(output,name+'.png')});
 }
 assert.deepEqual(errors,[]);const digest=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
 const report={status:'pass',browser:'Playwright; Browser plugin not available',default_results:data.views.documented.length,expanded_results:data.views.incomplete.length,total_venues:data.venues.length,subfields_checked:data.subfields.length,catalog_sha256:digest('data/venues.json'),html_sha256:digest('index.html'),checks:['identity and meaningful screen','three browsing modes','subfields','compare three and fourth-selection limit','URL reload and history','selection across filters','remove and clear','concerns remain visible','venue and publisher geography','lazy source panels','metric sorts','empty state','desktop/tablet/mobile','no browser errors']};
 fs.writeFileSync(path.join(root,'research/qa/browser-check.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
