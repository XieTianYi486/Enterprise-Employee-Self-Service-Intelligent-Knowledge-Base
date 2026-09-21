/**
 * 打印工具：生成一张纸质版申请单并在新窗口中直接打印。
 * 配合浏览器「打印」对话框，可另存为 PDF 或发送到打印机。
 */

/** 转义 HTML 特殊字符，避免用户输入破坏表单结构 */
export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const DIGITS = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
const SECTION_UNITS = ['', '拾', '佰', '仟']
const GROUP_UNITS = ['', '万', '亿']

function sectionToChinese(section: number): string {
  // 处理 [0, 9999] 内的四位数，如 1001 → 壹仟零壹
  let result = ''
  let zeroPending = false
  const s = String(section)
  for (let i = 0; i < s.length; i++) {
    const d = Number(s[i])
    if (d === 0) {
      zeroPending = true
      continue
    }
    if (zeroPending && result !== '') result += '零'
    zeroPending = false
    result += DIGITS[d] + SECTION_UNITS[s.length - 1 - i]
  }
  return result
}

function integerToChinese(intPart: number): string {
  const groups: number[] = []
  let tmp = intPart
  while (tmp > 0) {
    groups.unshift(tmp % 10000)
    tmp = Math.floor(tmp / 10000)
  }
  let result = ''
  for (let i = 0; i < groups.length; i++) {
    const gVal = groups[i]
    if (gVal === 0) continue
    // 非最高组且不足千位时，千位缺零要补「零」
    if (i > 0 && gVal < 1000) result += '零'
    result += sectionToChinese(gVal) + GROUP_UNITS[groups.length - 1 - i]
  }
  return result
}

/** 金额转人民币大写，如 123.45 → 壹佰贰拾叁元肆角伍分 */
export function amountInChinese(value: number): string {
  if (!Number.isFinite(value) || value < 0) return ''
  const totalFen = Math.round(value * 100)
  const intPart = Math.floor(totalFen / 100)
  const jiao = Math.floor((totalFen % 100) / 10)
  const fen = totalFen % 10

  let result = intPart > 0 ? integerToChinese(intPart) + '元' : ''
  if (jiao === 0 && fen === 0) {
    result = (result || '零元') + '整'
  } else {
    if (jiao > 0) {
      result += DIGITS[jiao] + '角'
    } else if (intPart > 0) {
      result += '零'
    }
    if (fen > 0) result += DIGITS[fen] + '分'
  }
  return result
}

/**
 * 打开新窗口渲染表单并自动唤起打印。
 * @param title 表单标题（同时作为页面标题）
 * @param bodyHtml 表单正文 HTML（不含 <html>/<head>）
 */
export function printForm(title: string, bodyHtml: string): void {
  const doc = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>${title}</title>
<style>
  @page { size: A4; margin: 13mm 15mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", "宋体", serif; color: #000; font-size: 14px; line-height: 1.6; padding: 26px 32px; }
  .form-title { text-align: center; font-family: "SimHei", "黑体", sans-serif; font-size: 26px; font-weight: bold; letter-spacing: 12px; margin: 8px 0 2px; }
  .form-no { text-align: right; font-size: 13px; margin: 0 0 14px; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 16px; }
  td { border: 1px solid #000; padding: 8px 10px; font-size: 14px; vertical-align: middle; word-break: break-all; }
  .label { width: 88px; background: #efefef; text-align: center; font-weight: bold; }
  .section { text-align: center; font-weight: bold; background: #efefef; letter-spacing: 3px; }
  .fill { height: 78px; vertical-align: top; }
  .blank { height: 28px; }
  .approval td { height: 92px; vertical-align: top; }
  .approval .label { vertical-align: middle; }
  .sign { line-height: 2; }
  .note { margin-top: 4px; font-size: 12px; color: #222; line-height: 2; }
  @media print { body { padding: 0; } }
</style>
</head>
<body>
<div class="form-title">${title}</div>
${bodyHtml}
<script>
  window.onload = function () { window.focus(); window.print(); };
<\/script>
</body>
</html>`

  const win = window.open('', '_blank')
  if (!win) return
  win.document.open()
  win.document.write(doc)
  win.document.close()
}