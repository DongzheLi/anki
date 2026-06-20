import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

// Renders one solution body in the format it was saved as:
//   - "code"     → a single fenced block run through markdown + highlight.js
//   - "markdown" → rendered markdown with highlighted code blocks
//   - "text"     → verbatim plain text in a <pre>, no parsing at all
export default function Content({ format, language, content }) {
  if (!content) return <p className="muted">No content.</p>;

  if (format === "text") {
    return (
      <div className="content">
        <pre className="plaintext">{content}</pre>
      </div>
    );
  }

  const md = format === "code" ? "```" + (language || "") + "\n" + content + "\n```" : content;
  return (
    <div className="content">
      <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{md}</ReactMarkdown>
    </div>
  );
}
