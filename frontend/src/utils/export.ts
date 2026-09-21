/**
 * 前端表格导出工具
 * 生成带 UTF-8 BOM 的 CSV，双击即可用 Excel 打开（中文不乱码）。
 * 零依赖，仅需传入表头与数据行的单元格原始值（null/undefined 自动转空串）。
 */

function escapeCell(value: unknown): string {
  let s: string
  if (value === null || value === undefined) {
    s = ''
  } else {
    s = String(value)
  }
  // 含逗号、引号、换行时需用双引号包裹，并双写内部引号
  if (/[",\r\n]/.test(s)) {
    s = '"' + s.replace(/"/g, '""') + '"'
  }
  return s
}

/**
 * 导出 CSV 并触发浏览器下载。
 * @param filename 下载文件名（不含扩展名）
 * @param headers  表头数组
 * @param rows     数据行（每行为单元格数组，长度应与 headers 一致）
 */
export function exportCsv(filename: string, headers: string[], rows: (unknown[])[]): void {
  const lines: string[] = [headers.map(escapeCell).join(',')]
  for (const row of rows) {
    lines.push(row.map(escapeCell).join(','))
  }
  // \uFEFF BOM：确保 Excel 正确识别 UTF-8 编码
  const content = '\uFEFF' + lines.join('\r\n')
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}