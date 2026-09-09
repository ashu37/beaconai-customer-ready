// A stand-in for the axios instance createShopifyClient returns. Pages are
// declared as arrays of items; a page that is not the last one carries a
// rel="next" Link header, which is the only signal the real client has that
// more rows exist.
function fakePagedClient(pagesByResource, { failOnPage } = {}) {
  const calls = [];
  return {
    calls,
    async get(path) {
      calls.push(path);
      const resource = path.replace(/^\//, "").split(".json")[0];
      const pages = pagesByResource[resource] || [[]];
      const pageInfoMatch = path.match(/[?&]page_info=([^&]+)/);
      const index = pageInfoMatch ? Number(pageInfoMatch[1]) : 0;

      if (failOnPage && failOnPage.resource === resource && failOnPage.page === index) {
        throw new Error(`Shopify ${resource} page ${index} failed`);
      }

      const isLast = index >= pages.length - 1;
      return {
        data: { [resource]: pages[index] || [] },
        headers: isLast
          ? {}
          : { link: `</${resource}.json?limit=250&page_info=${index + 1}>; rel="next"` },
      };
    },
  };
}

function items(n, offset = 0) {
  return Array.from({ length: n }, (_, i) => ({ id: offset + i + 1 }));
}

module.exports = { fakePagedClient, items };
