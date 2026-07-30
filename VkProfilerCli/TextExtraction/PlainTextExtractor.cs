using System.IO;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Reads a UTF-8 text file verbatim. Also used as the fallback for unknown extensions.
    /// </summary>
    public class PlainTextExtractor : ITextExtractor
    {
        public string[] Extensions => new[] { ".txt", ".text" };

        public string Extract(string filePath) => File.ReadAllText(filePath);
    }
}
