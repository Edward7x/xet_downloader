// ==UserScript==
// @name         小鹅通 m3u8 导出
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  自动识别主 m3u8 + 课程标题，导出 JSON
// @author       Eddie7x
// @match        *://*.xiaoeknow.com/*
// @match        *://*.h5.xet.citv.cn/*
// @grant        GM_download
// ==/UserScript==

(function () {
    'use strict';

    const pool = new Map();

    function getTitle() {
        const titleEl = document.querySelector(".title-row .title.new_title");
        if (titleEl && titleEl.innerText.trim().length > 0) {
            return titleEl.innerText.trim();
        }

        // fallback 老方案
        const selectors = ['h1','.course-title','.lesson-title','.title'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.innerText.trim().length > 2) {
                return el.innerText.trim();
            }
        }

        // 最后 fallback 页面 title
        return document.title.replace(/[-_｜|].*/, '').trim();
    }


    function score(url) {
        let s = url.length / 10;
        if (/master|index|playlist/i.test(url)) s += 30;
        if (/token|sign|expires/i.test(url)) s += 20;
        return Math.floor(s);
    }

    function collect(url) {
        if (!url || !url.includes('.m3u8')) return;
        if (!pool.has(url)) {
            pool.set(url, { url, score: score(url) });
        }
    }

    // hook fetch / xhr
    const _fetch = window.fetch;
    window.fetch = function (...args) {
        collect(args[0]?.url || args[0]);
        return _fetch.apply(this, args);
    };
    const _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (m, url) {
        collect(url);
        return _open.apply(this, arguments);
    };

    // UI 按钮
    const btn = document.createElement('div');
    btn.innerText = '导出本课';
    btn.style.cssText = `
    position: fixed;
    right: 20px;
    bottom: 80px;
    z-index: 99999;
    background: #1e80ff;
    color: #fff;
    padding: 12px 16px;
    border-radius: 10px;
    cursor: pointer;
  `;

    btn.onclick = () => {
        if (pool.size === 0) {
            alert('请先播放课程');
            return;
        }

        const best = [...pool.values()].sort((a, b) => b.score - a.score)[0];
        const data = [{
            title: getTitle(),
            m3u8: best.url
        }];

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        GM_download({
            url,
            name: 'm3u8_list.json'
        });
    };

    document.body.appendChild(btn);
})();
