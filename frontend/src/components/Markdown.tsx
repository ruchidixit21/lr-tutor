// Renders the subset of markdown the agent produces: bold, bullets, horizontal rules.
// Avoids a library dependency for a small, known set of patterns.

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export default function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === "---") {
      nodes.push(<hr key={i} className="border-gray-200 my-2" />);
      i++;
      continue;
    }

    if (line.trim().startsWith("- ")) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && lines[i].trim().startsWith("- ")) {
        items.push(
          <li key={i} className="ml-4 list-disc">
            {renderInline(lines[i].trim().slice(2))}
          </li>
        );
        i++;
      }
      nodes.push(<ul key={`ul-${i}`} className="space-y-1">{items}</ul>);
      continue;
    }

    if (line.trim() === "") {
      nodes.push(<div key={i} className="h-2" />);
      i++;
      continue;
    }

    nodes.push(<p key={i}>{renderInline(line)}</p>);
    i++;
  }

  return <div className="space-y-1 text-sm leading-relaxed text-gray-800">{nodes}</div>;
}
