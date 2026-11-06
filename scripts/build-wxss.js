/**
 * 把网页版 app.css 转成小程序 wxss：
 *  - px → rpx（375 设计稿 1px = 2rpx）
 *  - :root → page
 *  - 去掉 @media、hover、cursor、backdrop-filter、.device/.screen 外壳
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'frontend/src/styles/app.css');
const OUT = path.join(ROOT, 'miniprogram/base.wxss');

let css = fs.readFileSync(SRC, 'utf8');

// 1) 去掉 @media 整块（小程序不支持）
css = css.replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '');

// 2) 去掉桌面外壳相关规则
['.app-shell', '.device', '.device::after', '.screen', '.desk-note', '.capsule'].forEach((sel) => {
  const re = new RegExp(
    `\\${sel[0]}[^{]*\\{[^}]*\\}`,
    'g'
  );
  // 简化：按选择器首词匹配整条规则
  css = css.replace(new RegExp(`(^|\\n)\\s*\\${sel.replace('.', '.')}[^{}]*\\{[^{}]*\\}`, 'g'), '\n');
});

// 3) :root → page
css = css.replace(/:root\s*\{/, 'page {');

// 4) 去掉 web 专属属性
css = css
  .replace(/[^\n;{}]*cursor:\s*[^;]+;/g, '')
  .replace(/[^\n;{}]*-webkit-[^;]+;/g, '')
  .replace(/[^\n;{}]*backdrop-filter:[^;]+;/g, '')
  .replace(/[^\n;{}]*scroll-behavior:[^;]+;/g, '')
  .replace(/[^\n;{}]*overscroll-behavior:[^;]+;/g, '')
  .replace(/[^\n;{}]*isolation:[^;]+;/g, '');

// 5) 去掉 :hover 规则与 ::-webkit-scrollbar
css = css.replace(/[^{}]*:hover[^{}]*\{[^}]*\}/g, '');
css = css.replace(/[^{}]*::-webkit-scrollbar[^{}]*\{[^}]*\}/g, '');

// 6) px → rpx（×2）
css = css.replace(/(-?\d*\.?\d+)px/g, (m, n) => {
  const v = parseFloat(n);
  if (v === 0) return '0';
  return `${Math.round(v * 2 * 100) / 100}rpx`;
});

// 7) 清掉连续空行
css = css.replace(/\n{3,}/g, '\n\n');

// 8) 通配符选择器在小程序里支持不稳，换成显式元素列表（保留 box-sizing 语义）
css = css.replace(/(^|\n)\s*\*\s*\{/g, '$1view, text, image, input, button, scroll-view, textarea {');

// 9) 括号平衡兜底：正则删除规则时可能留下孤立的 }，深度为 0 的 } 直接丢掉
function sanitizeBraces(text) {
  let depth = 0;
  let out = '';
  for (const ch of text) {
    if (ch === '{') {
      depth += 1;
      out += ch;
    } else if (ch === '}') {
      if (depth > 0) {
        depth -= 1;
        out += ch;
      }
      // depth === 0 时丢弃这个多余的 }，并吞掉它前面的空行
      else {
        out = out.replace(/\n\s*$/, '\n');
      }
    } else {
      out += ch;
    }
  }
  return { text: out, depth };
}

const sanitized = sanitizeBraces(css);
css = sanitized.text;
if (sanitized.depth !== 0) {
  console.error(`✗ 括号仍不平衡，剩余未闭合 ${sanitized.depth} 个 {`);
  process.exit(1);
}

const banner = `/* 由 scripts/build-wxss.js 从 frontend/src/styles/app.css 自动生成，勿手改 */
/* 375 设计稿：1px → 2rpx */

`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, banner + css.trim() + '\n', 'utf8');
console.log(`wxss 已生成：${OUT}（${(banner + css).length} 字符）`);
