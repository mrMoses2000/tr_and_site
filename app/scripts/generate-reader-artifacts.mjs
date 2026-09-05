#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const booksSourceRoot = path.join(appRoot, 'src', 'data', 'books');
const bundledCatalogPath = path.join(appRoot, 'src', 'data', 'library', 'generatedCatalog.json');
const publicBooksRoot = path.join(appRoot, 'public', 'books');
const publicCatalogPath = path.join(appRoot, 'public', 'catalog.json');

const jsonText = (value) => `${JSON.stringify(value, null, 2)}\n`;

async function writeJson(destination, value) {
  await mkdir(path.dirname(destination), { recursive: true });
  await writeFile(destination, jsonText(value), 'utf8');
}

function assertManifest(manifest, sourcePath) {
  if (!manifest || typeof manifest !== 'object'
      || typeof manifest.slug !== 'string'
      || !Array.isArray(manifest.pages)
      || manifest.pages.length === 0) {
    throw new Error(`Invalid reader manifest: ${sourcePath}`);
  }
  const numbers = manifest.pages.map((page) => page?.pageNumber);
  if (numbers.some((number) => !Number.isInteger(number))
      || new Set(numbers).size !== numbers.length) {
    throw new Error(`Manifest has invalid or duplicate page numbers: ${sourcePath}`);
  }
}

function searchEntriesForPage(page) {
  const entries = [];
  for (const paragraph of page.paragraphs ?? []) {
    for (const [language, text] of [['ru', paragraph.ru], ['en', paragraph.en]]) {
      if (typeof text === 'string' && text.length > 0) {
        entries.push({
          pageNumber: page.pageNumber,
          paragraphId: paragraph.id,
          targetType: 'paragraph',
          language,
          chapterTitle: page.chapterTitle,
          text,
        });
      }
    }
  }
  for (const footnote of page.footnotes ?? []) {
    for (const [language, text] of [['ru', footnote.textRu], ['en', footnote.textEn]]) {
      if (typeof text === 'string' && text.length > 0) {
        entries.push({
          pageNumber: page.pageNumber,
          paragraphId: `fn-${footnote.id}`,
          targetType: 'footnote',
          footnoteId: footnote.id,
          language,
          chapterTitle: language === 'ru' ? `Сноска ${footnote.id}` : `Footnote ${footnote.id}`,
          text,
        });
      }
    }
  }
  return entries;
}

function catalogEntry(manifest, releaseId, baseUrl) {
  return {
    slug: manifest.slug,
    title: manifest.title ?? manifest.slug,
    titleRu: manifest.titleRu ?? manifest.title ?? manifest.slug,
    author: manifest.author ?? 'Unknown',
    authorRu: manifest.authorRu ?? manifest.author ?? 'Unknown',
    totalPages: manifest.pages.length,
    releaseId,
    releaseManaged: true,
    manifestUrl: `${baseUrl}/manifest.json`,
    pagesIndexUrl: `${baseUrl}/pages-index.json`,
    searchIndexUrl: `${baseUrl}/search-index.json`,
    pageChunkPattern: `${baseUrl}/pages/page-{page}.json`,
    scanPattern: `/scans/${manifest.slug}/page_{page}.webp`,
  };
}

async function main() {
  const bundled = JSON.parse(await readFile(bundledCatalogPath, 'utf8'));
  const entriesBySlug = new Map(
    (Array.isArray(bundled.books) ? bundled.books : []).map((book) => [book.slug, book]),
  );
  const sourceDirectories = (await readdir(booksSourceRoot, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();

  await rm(publicBooksRoot, { recursive: true, force: true });
  for (const directoryName of sourceDirectories) {
    const sourcePath = path.join(booksSourceRoot, directoryName, 'manifest.json');
    let source;
    try {
      source = await readFile(sourcePath);
    } catch (error) {
      if (error?.code === 'ENOENT') continue;
      throw error;
    }
    const manifest = JSON.parse(source.toString('utf8'));
    assertManifest(manifest, sourcePath);
    if (manifest.slug !== directoryName) {
      throw new Error(`Manifest slug does not match its directory: ${sourcePath}`);
    }

    const digest = createHash('sha256').update(source).digest('hex');
    const releaseId = manifest.releaseId ?? `rel-${manifest.slug}-${digest.slice(0, 12)}`;
    const baseUrl = `/books/${manifest.slug}/releases/${releaseId}`;
    const releaseRoot = path.join(publicBooksRoot, manifest.slug, 'releases', releaseId);
    const start = Math.min(...manifest.pages.map((page) => page.pageNumber));
    const end = Math.max(...manifest.pages.map((page) => page.pageNumber));
    const searchEntries = [];
    const pageIndexEntries = [];

    for (const page of manifest.pages) {
      const chunk = {
        schemaVersion: '1.0',
        bookSlug: manifest.slug,
        releaseId,
        ...page,
      };
      const relativeChunkUrl = `pages/page-${page.pageNumber}.json`;
      const chunkText = jsonText(chunk);
      await writeJson(path.join(releaseRoot, relativeChunkUrl), chunk);
      pageIndexEntries.push({
        pageNumber: page.pageNumber,
        chunkUrl: relativeChunkUrl,
        checksum: createHash('sha256').update(chunkText).digest('hex'),
        byteSize: Buffer.byteLength(chunkText),
        blockCount: Array.isArray(page.paragraphs) ? page.paragraphs.length : 0,
        footnoteCount: Array.isArray(page.footnotes) ? page.footnotes.length : 0,
      });
      searchEntries.push(...searchEntriesForPage(page));
    }

    const pagesIndexUrl = `${baseUrl}/pages-index.json`;
    const searchIndexUrl = `${baseUrl}/search-index.json`;
    await writeJson(path.join(releaseRoot, 'pages-index.json'), {
      schemaVersion: '1.0',
      bookSlug: manifest.slug,
      releaseId,
      pageRange: { start, end },
      pages: pageIndexEntries,
      searchIndexUrl,
    });
    await writeJson(path.join(releaseRoot, 'search-index.json'), {
      schemaVersion: '1.0',
      bookSlug: manifest.slug,
      releaseId,
      pageRange: { start, end },
      entries: searchEntries,
    });
    await writeJson(path.join(releaseRoot, 'manifest.json'), {
      ...manifest,
      schemaVersion: manifest.schemaVersion ?? '2.0',
      releaseId,
      startPage: start,
      endPage: end,
      totalPages: manifest.pages.length,
      pagesIndexUrl,
      searchIndexUrl,
      pageChunkPattern: `${baseUrl}/pages/page-{page}.json`,
      manifestUrl: `${baseUrl}/manifest.json`,
      pages: [],
    });
    entriesBySlug.set(manifest.slug, catalogEntry(manifest, releaseId, baseUrl));
  }

  const catalog = {
    schemaVersion: '1.0',
    books: [...entriesBySlug.values()].sort((left, right) => left.slug.localeCompare(right.slug)),
  };
  await writeJson(bundledCatalogPath, catalog);
  await writeJson(publicCatalogPath, catalog);
}

await main();
