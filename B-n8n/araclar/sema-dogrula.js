#!/usr/bin/env node
// workflow.json'ı n8n'in GERÇEK düğüm tanımlarına karşı doğrular — n8n kurmadan.
//
// Kaynak: npm'deki `n8n-nodes-base` paketinin `dist/types/nodes.json` dosyası (n8n editörünün
// kullandığı tanımlar). Paket `npm pack` ile yalnızca dosya olarak indirilir (~9 MB, bağımlılık
// kurulmaz) ve B-n8n/.cache/ altında tutulur (.gitignore'da).
//
// Denetlenenler:
//   · düğüm tipi ve typeVersion gerçekten var mı
//   · her parametre adı tanımlı mı, displayOptions'a göre bu ayarlarda görünür mü
//     (görünmeyen parametre n8n'de sessizce yok sayılır → yanlış yapılandırma)
//   · options değerleri, boolean/number tipleri, collection / fixedCollection iç yapıları
//   · resourceLocator modu, resourceMapper eşleme modu, filter koşul yapısı
//   · düğüm ayarları (onError, retry) ve bağlantılarda çıkış sayısı
//
// Kullanım: node araclar/sema-dogrula.js [workflow.json]      (çıkış kodu 1 = hata var)

'use strict';

const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const KOK = path.resolve(__dirname, '..');
const N8N_SURUMU = '2.15.1'; // tekrarlanabilirlik için sabitlendi
const ONBELLEK = path.join(KOK, '.cache', `n8n-nodes-base-${N8N_SURUMU}`);

function tanimlariYukle() {
  const hedef = path.join(ONBELLEK, 'nodes.json');
  if (!fs.existsSync(hedef)) {
    fs.mkdirSync(ONBELLEK, { recursive: true });
    const tgz = execFileSync('npm', ['pack', `n8n-nodes-base@${N8N_SURUMU}`, '--silent'], { cwd: ONBELLEK })
      .toString().trim().split('\n').pop();
    execFileSync('tar', ['-xzf', tgz, '--strip-components=3', 'package/dist/types/nodes.json'], { cwd: ONBELLEK });
    fs.unlinkSync(path.join(ONBELLEK, tgz));
  }
  return JSON.parse(fs.readFileSync(hedef, 'utf8'));
}

// ---------------------------------------------------------------- displayOptions

function kosulSaglaniyor(beklenen, deger) {
  if (beklenen && typeof beklenen === 'object' && '_cnd' in beklenen) {
    const [op, arg] = Object.entries(beklenen._cnd)[0];
    switch (op) {
      case 'eq': return deger === arg;
      case 'not': return deger !== arg;
      case 'gte': return deger >= arg;
      case 'lte': return deger <= arg;
      case 'gt': return deger > arg;
      case 'lt': return deger < arg;
      case 'between': return deger >= arg.from && deger <= arg.to;
      case 'startsWith': return String(deger).startsWith(arg);
      case 'endsWith': return String(deger).endsWith(arg);
      case 'includes': return String(deger).includes(arg);
      case 'regex': return new RegExp(arg).test(String(deger));
      case 'exists': return deger !== undefined;
      default: return true; // bilinmeyen koşul: görünür kabul et (yanlış alarm üretme)
    }
  }
  return deger === beklenen;
}

function gorunur(ozellik, degerler, baglam) {
  const d = ozellik.displayOptions;
  if (!d) return true;
  const al = (anahtar) => {
    if (anahtar === '@version') return baglam.surum;
    if (anahtar.startsWith('/')) return baglam.kok[anahtar.slice(1)];
    return degerler[anahtar];
  };
  for (const [anahtar, liste] of Object.entries(d.show || {})) {
    if (!liste.some((b) => kosulSaglaniyor(b, al(anahtar)))) return false;
  }
  for (const [anahtar, liste] of Object.entries(d.hide || {})) {
    if (liste.some((b) => kosulSaglaniyor(b, al(anahtar)))) return false;
  }
  return true;
}

// Verilmeyen parametrelerin varsayılanlarını ekler (displayOptions onlara da bakar; ör. resource="sheet").
function etkinDegerler(ozellikler, verilen, baglam) {
  const d = { ...verilen };
  for (let tur = 0; tur < 3; tur++) {
    for (const o of ozellikler) {
      if (!(o.name in d) && o.default !== undefined && gorunur(o, d, { ...baglam, kok: baglam.kok || d })) {
        d[o.name] = o.default;
      }
    }
  }
  return d;
}

// ---------------------------------------------------------------- parametre doğrulama

const ifadeMi = (deger) => typeof deger === 'string' && deger.startsWith('=');
const nesneMi = (deger) => deger !== null && typeof deger === 'object' && !Array.isArray(deger);

function parametreleriDogrula(ozellikler, verilen, yol, baglam, hatalar) {
  const etkin = etkinDegerler(ozellikler, verilen, baglam);
  const altBaglam = { ...baglam, kok: baglam.kok || etkin };
  for (const [ad, deger] of Object.entries(verilen)) {
    const adaylar = ozellikler.filter((o) => o.name === ad);
    if (adaylar.length === 0) {
      const gecerli = [...new Set(ozellikler.map((o) => o.name))].join(', ');
      hatalar.push(`${yol}.${ad}: bilinmeyen parametre (geçerli: ${gecerli})`);
      continue;
    }
    const gorunenler = adaylar.filter((o) => gorunur(o, etkin, altBaglam));
    if (gorunenler.length === 0) {
      hatalar.push(`${yol}.${ad}: bu ayarlarla görünmüyor (displayOptions) — n8n bu değeri yok sayar`);
      continue;
    }
    // Aynı ad birden çok tanımda olabilir (ör. farklı sürüm aralıkları); birine uyması yeterli.
    const denemeler = gorunenler.map((o) => {
      const alt = [];
      degeriDogrula(o, deger, `${yol}.${ad}`, altBaglam, alt);
      return alt;
    });
    if (!denemeler.some((alt) => alt.length === 0)) hatalar.push(...denemeler[0]);
  }
}

function degeriDogrula(o, deger, yol, baglam, hatalar) {
  if (ifadeMi(deger) && !['fixedCollection', 'collection'].includes(o.type)) return; // ifade: çalışmada çözülür
  switch (o.type) {
    case 'options': {
      if (!o.options.some((s) => s.value === deger)) {
        hatalar.push(`${yol}: geçersiz değer ${JSON.stringify(deger)} (geçerli: ${o.options.map((s) => s.value).join(', ')})`);
      }
      return;
    }
    case 'multiOptions':
      if (!Array.isArray(deger)) hatalar.push(`${yol}: dizi olmalı`);
      else deger.filter((v) => !o.options.some((s) => s.value === v))
        .forEach((v) => hatalar.push(`${yol}: geçersiz seçenek ${JSON.stringify(v)}`));
      return;
    case 'boolean':
      if (typeof deger !== 'boolean') hatalar.push(`${yol}: boolean olmalı, ${typeof deger} verildi`);
      return;
    case 'number':
      if (typeof deger !== 'number') hatalar.push(`${yol}: number olmalı, ${typeof deger} verildi`);
      return;
    case 'string':
    case 'json':
      if (typeof deger !== 'string') hatalar.push(`${yol}: string olmalı, ${typeof deger} verildi`);
      return;
    case 'collection':
      if (!nesneMi(deger)) { hatalar.push(`${yol}: nesne olmalı`); return; }
      parametreleriDogrula(o.options, deger, yol, baglam, hatalar);
      return;
    case 'fixedCollection': {
      if (!nesneMi(deger)) { hatalar.push(`${yol}: nesne olmalı`); return; }
      const coklu = Boolean(o.typeOptions && o.typeOptions.multipleValues);
      for (const [grupAdi, grupDegeri] of Object.entries(deger)) {
        const grup = o.options.find((g) => g.name === grupAdi);
        if (!grup) {
          hatalar.push(`${yol}.${grupAdi}: bilinmeyen grup (geçerli: ${o.options.map((g) => g.name).join(', ')})`);
          continue;
        }
        if (coklu && !Array.isArray(grupDegeri)) { hatalar.push(`${yol}.${grupAdi}: dizi olmalı (multipleValues)`); continue; }
        if (!coklu && !nesneMi(grupDegeri)) { hatalar.push(`${yol}.${grupAdi}: nesne olmalı`); continue; }
        (coklu ? grupDegeri : [grupDegeri]).forEach((oge, i) => parametreleriDogrula(
          grup.values, oge, coklu ? `${yol}.${grupAdi}[${i}]` : `${yol}.${grupAdi}`, baglam, hatalar,
        ));
      }
      return;
    }
    case 'resourceLocator': {
      if (!nesneMi(deger) || deger.__rl !== true) { hatalar.push(`${yol}: resourceLocator nesnesi olmalı ({__rl: true, mode, value})`); return; }
      const modlar = (o.modes || []).map((m) => m.name);
      if (modlar.length && !modlar.includes(deger.mode)) hatalar.push(`${yol}.mode: geçersiz "${deger.mode}" (geçerli: ${modlar.join(', ')})`);
      return;
    }
    case 'resourceMapper':
      if (!nesneMi(deger)) { hatalar.push(`${yol}: nesne olmalı`); return; }
      if (!['defineBelow', 'autoMapInputData'].includes(deger.mappingMode)) hatalar.push(`${yol}.mappingMode: geçersiz "${deger.mappingMode}"`);
      if (deger.mappingMode === 'defineBelow' && !nesneMi(deger.value)) hatalar.push(`${yol}.value: nesne olmalı`);
      return;
    case 'filter':
      if (!nesneMi(deger) || !Array.isArray(deger.conditions)) { hatalar.push(`${yol}: filter yapısı ({conditions: [...], combinator}) olmalı`); return; }
      if (!['and', 'or'].includes(deger.combinator)) hatalar.push(`${yol}.combinator: "and" ya da "or" olmalı`);
      deger.conditions.forEach((k, i) => {
        if (!k.operator || typeof k.operator.type !== 'string' || typeof k.operator.operation !== 'string') {
          hatalar.push(`${yol}.conditions[${i}].operator: {type, operation} olmalı`);
        }
      });
      return;
    default:
      // notice, hidden, credentialsSelect, cron vb.: yapısal kontrol gerektirmez
  }
}

// ---------------------------------------------------------------- düğüm ve bağlantılar

const ON_ERROR = ['stopWorkflow', 'continueRegularOutput', 'continueErrorOutput'];

function tanimBul(tanimlar, dugum) {
  const ad = dugum.type.replace(/^n8n-nodes-base\./, '');
  const adaylar = tanimlar.filter((t) => t.name === ad);
  const tanim = adaylar.find((t) => [].concat(t.version).includes(dugum.typeVersion));
  const surumler = adaylar.flatMap((t) => [].concat(t.version)).sort((a, b) => a - b);
  return { ad, tanim, surumler };
}

function cikisSayisi(dugum, tanim, ad) {
  let sayi = null;
  if (Array.isArray(tanim.outputs)) sayi = tanim.outputs.length;
  else if (ad === 'if') sayi = 2;
  else if (ad === 'switch') {
    const kurallar = ((dugum.parameters.rules || {}).values || []).length;
    sayi = kurallar + ((dugum.parameters.options || {}).fallbackOutput === 'extra' ? 1 : 0);
  }
  if (sayi !== null && dugum.onError === 'continueErrorOutput') sayi += 1;
  return sayi;
}

function dogrula(workflow, tanimlar) {
  const rapor = [];
  const cikislar = {};
  for (const dugum of workflow.nodes) {
    const hatalar = [];
    const { ad, tanim, surumler } = tanimBul(tanimlar, dugum);
    if (!tanim) {
      hatalar.push(surumler.length ? `typeVersion ${dugum.typeVersion} yok (mevcut: ${surumler.join(', ')})` : `bilinmeyen düğüm tipi ${dugum.type}`);
      rapor.push({ dugum, ad, hatalar });
      continue;
    }
    parametreleriDogrula(tanim.properties, dugum.parameters || {}, 'parameters',
      { surum: dugum.typeVersion, kok: null }, hatalar);
    if (dugum.onError !== undefined && !ON_ERROR.includes(dugum.onError)) hatalar.push(`onError: geçersiz "${dugum.onError}"`);
    if (dugum.retryOnFail !== undefined && typeof dugum.retryOnFail !== 'boolean') hatalar.push('retryOnFail: boolean olmalı');
    if (dugum.maxTries !== undefined && !(dugum.maxTries >= 2 && dugum.maxTries <= 5)) hatalar.push('maxTries: 2–5 arası olmalı');
    if (dugum.waitBetweenTries !== undefined && !(dugum.waitBetweenTries >= 0 && dugum.waitBetweenTries <= 5000)) {
      hatalar.push('waitBetweenTries: 0–5000 ms arası olmalı');
    }
    cikislar[dugum.name] = cikisSayisi(dugum, tanim, ad);
    // Kimlik gereksinimleri de displayOptions'a bağlıdır (ör. googleApi yalnızca servis hesabında).
    const etkin = etkinDegerler(tanim.properties, dugum.parameters || {}, { surum: dugum.typeVersion, kok: null });
    const kimlik = (tanim.credentials || [])
      .filter((c) => c.required && gorunur(c, etkin, { surum: dugum.typeVersion, kok: etkin }))
      .map((c) => c.name);
    rapor.push({ dugum, ad, hatalar, kimlik });
  }

  const baglantiHatalari = [];
  const adlar = new Set(workflow.nodes.map((n) => n.name));
  for (const [kaynak, { main = [] }] of Object.entries(workflow.connections || {})) {
    if (!adlar.has(kaynak)) baglantiHatalari.push(`bağlantı kaynağı yok: ${kaynak}`);
    const beklenen = cikislar[kaynak];
    if (beklenen != null && main.length > beklenen) {
      baglantiHatalari.push(`${kaynak}: ${main.length} çıkış bağlı, düğümün ${beklenen} çıkışı var`);
    }
    main.flat().forEach((h) => { if (!adlar.has(h.node)) baglantiHatalari.push(`${kaynak} → bilinmeyen hedef ${h.node}`); });
  }
  return { rapor, cikislar, baglantiHatalari };
}

module.exports = { dogrula, tanimlariYukle, N8N_SURUMU };

if (require.main === module) {
  const dosya = path.resolve(process.argv[2] || path.join(KOK, 'workflow.json'));
  const workflow = JSON.parse(fs.readFileSync(dosya, 'utf8'));
  const tanimlar = tanimlariYukle();
  const { rapor, cikislar, baglantiHatalari } = dogrula(workflow, tanimlar);
  console.log(`n8n-nodes-base@${N8N_SURUMU} tanımları yüklendi (${tanimlar.length} düğüm tanımı)`);
  console.log(`Doğrulanan: ${path.relative(process.cwd(), dosya)}\n`);
  let hataSayisi = 0;
  for (const { dugum, ad, hatalar, kimlik } of rapor) {
    const parametreSayisi = JSON.stringify(dugum.parameters || {}).match(/"[^"]+":/g)?.length || 0;
    const ek = [
      `${parametreSayisi} alan`,
      cikislar[dugum.name] != null ? `${cikislar[dugum.name]} çıkış` : null,
      kimlik && kimlik.length ? `kimlik: ${kimlik.join(', ')}` : null,
    ].filter(Boolean).join(' · ');
    console.log(`${hatalar.length ? '✖' : '✔'} ${dugum.name.padEnd(38)} ${`${ad} v${dugum.typeVersion}`.padEnd(22)} ${ek}`);
    hatalar.forEach((h) => console.log(`    └ ${h}`));
    hataSayisi += hatalar.length;
  }
  baglantiHatalari.forEach((h) => console.log(`✖ bağlantı: ${h}`));
  hataSayisi += baglantiHatalari.length;
  const bagSayisi = Object.values(workflow.connections).reduce((t, c) => t + c.main.flat().length, 0);
  console.log(`\n${rapor.length - rapor.filter((r) => r.hatalar.length).length}/${rapor.length} düğüm geçerli · `
    + `${bagSayisi} bağlantı · ${hataSayisi} hata`);
  process.exitCode = hataSayisi ? 1 : 0;
}
