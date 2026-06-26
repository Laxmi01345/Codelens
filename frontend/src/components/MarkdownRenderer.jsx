import MermaidDiagram from './MermaidDiagram';

function parseMermaidBlocks(content) {
  const blocks = [];
  const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/gi;

  let lastIndex = 0;
  let match;

  while ((match = mermaidRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', content: content.slice(lastIndex, match.index) });
    }
    blocks.push({ type: 'mermaid', content: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    blocks.push({ type: 'text', content: content.slice(lastIndex) });
  }

  return blocks;
}

function renderInlineMarkdown(text) {
  return text
    .replace(/`([^`]+)`/g, '<code class="bg-slate-700/50 px-1.5 py-0.5 rounded text-emerald-400 text-sm font-mono">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="text-slate-300">$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-emerald-400 hover:underline">$1</a>');
}

function renderMarkdown(content) {
  const lines = content.split('\n');
  const html = [];
  let inList = false;
  let inTable = false;
  let inCodeBlock = false;
  let codeBlockContent = [];
  let codeBlockLang = '';

  for (const line of lines) {
    const trimmed = line.trim();

    // Handle code blocks
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        // End of code block - render it
        html.push(`<pre class="bg-slate-900/80 rounded-xl p-4 my-4 overflow-x-auto border border-slate-700/50"><code class="text-sm text-slate-200 font-mono leading-relaxed">${codeBlockContent.join('\n')}</code></pre>`);
        codeBlockContent = [];
        inCodeBlock = false;
      } else {
        // Start of code block
        inCodeBlock = true;
        codeBlockLang = trimmed.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      // Preserve code block content exactly as-is (including tree characters)
      codeBlockContent.push(line);
      continue;
    }

    // Handle other markdown elements
    if (trimmed.startsWith('### ')) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inTable) { html.push('</table>'); inTable = false; }
      html.push(`<h3 class="text-xl font-semibold text-white mt-6 mb-3">${renderInlineMarkdown(trimmed.slice(4))}</h3>`);
    } else if (trimmed.startsWith('## ')) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inTable) { html.push('</table>'); inTable = false; }
      html.push(`<h2 class="text-2xl font-bold text-white mt-8 mb-4">${renderInlineMarkdown(trimmed.slice(3))}</h2>`);
    } else if (trimmed.startsWith('# ')) {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inTable) { html.push('</table>'); inTable = false; }
      html.push(`<h1 class="text-3xl font-bold text-white mt-8 mb-4">${renderInlineMarkdown(trimmed.slice(2))}</h1>`);
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) { html.push('<ul class="list-disc list-inside space-y-1 my-3 text-slate-300">'); inList = true; }
      html.push(`<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`);
    } else if (trimmed.startsWith('|')) {
      if (!inTable) { html.push('<table class="w-full my-4 border-collapse"><thead><tr>'); inTable = true; }
      if (trimmed.includes('---')) continue;
      const cells = trimmed.split('|').filter((c) => c.trim()).map((c) => c.trim());
      const isHeader = !html.some(h => h.includes('<td'));
      if (isHeader) {
        html.push(`<th class="px-4 py-2 bg-slate-800 text-left text-white border border-slate-700">${cells.map((c) => renderInlineMarkdown(c)).join('</th><th class="px-4 py-2 bg-slate-800 text-left text-white border border-slate-700">')}</th></tr></thead><tbody>`);
      } else {
        html.push(`<tr>${cells.map((c) => `<td class="px-4 py-2 border border-slate-700 text-slate-300">${renderInlineMarkdown(c)}</td>`).join('')}</tr>`);
      }
    } else if (trimmed === '') {
      if (inList) { html.push('</ul>'); inList = false; }
      if (inTable) { html.push('</tbody></table>'); inTable = false; }
    } else if (trimmed) {
      html.push(`<p class="text-slate-300 leading-relaxed my-3">${renderInlineMarkdown(trimmed)}</p>`);
    }
  }

  if (inList) html.push('</ul>');
  if (inTable) html.push('</tbody></table>');

  return html.join('\n');
}

export default function MarkdownRenderer({ content }) {
  if (!content) {
    return <div className="text-slate-400 py-8 text-center">No content to display</div>;
  }

  const blocks = parseMermaidBlocks(content);

  return (
    <div className="markdown-content">
      {blocks.map((block, i) =>
        block.type === 'mermaid' ? (
          <MermaidDiagram key={`mermaid-${i}`} code={block.content} className="my-6" />
        ) : (
          <div key={`text-${i}`} dangerouslySetInnerHTML={{ __html: renderMarkdown(block.content) }} />
        )
      )}
    </div>
  );
}
