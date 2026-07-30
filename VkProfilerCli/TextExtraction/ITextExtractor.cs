namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Extracts plain, analysable text from a file of a particular format.
    /// </summary>
    public interface ITextExtractor
    {
        /// <summary>File extensions this extractor handles, lower-case, including the leading dot (e.g. ".pdf").</summary>
        string[] Extensions { get; }

        /// <summary>Read <paramref name="filePath"/> and return its text content.</summary>
        string Extract(string filePath);
    }
}
