using System.IO;
using Markdig;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Converts a Markdown document to plain text, dropping syntax (headings, emphasis,
    /// links, code fences, list markers) so only the prose is profiled.
    /// </summary>
    public class MarkdownTextExtractor : ITextExtractor
    {
        public string[] Extensions => new[] { ".md", ".markdown" };

        public string Extract(string filePath)
        {
            string markdown = File.ReadAllText(filePath);
            return Markdown.ToPlainText(markdown);
        }
    }
}
