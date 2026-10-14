const s = require("../../utils/service");
const { retrieve } = require("../../utils/retrieval");
const kb = require("../../data/knowledge");
Page({
  data: {
    query: "暴雨",
    results: [],
    count: kb.documents.length,
    chunks: kb.documents.reduce((n, d) => n + d.chunks.length, 0),
  },
  onLoad() {
    this.search();
  },
  input(e) {
    this.setData({ query: e.detail.value });
  },
  search() {
    this.setData({
      results: retrieve(this.data.query, kb.documents, 10).map((h) => ({
        ...h,
        title: s.toSimple(h.title),
        text: s.toSimple(h.text),
        publisher: s.toSimple(h.publisher),
        time: s.time(h.importedAt),
      })),
    });
  },
  copy(e) {
    s.copy(e.currentTarget.dataset.url);
  },
});
