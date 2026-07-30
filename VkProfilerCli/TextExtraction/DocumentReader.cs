using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>Raised when a file cannot be read or produces no analysable text.</summary>
    public class DocumentReadException : Exception
    {
        public DocumentReadException(string message) : base(message) { }
        public DocumentReadException(string message, Exception inner) : base(message, inner) { }
    }

    /// <summary>
    /// Chooses a <see cref="ITextExtractor"/> based on file extension and returns the
    /// extracted text. Unknown extensions fall back to reading the file as UTF-8 text.
    /// </summary>
    public class DocumentReader
    {
        private readonly Dictionary<string, ITextExtractor> _byExtension;
        private readonly ITextExtractor _fallback;

        public DocumentReader()
            : this(new ITextExtractor[]
            {
                new PlainTextExtractor(),
                new MarkdownTextExtractor(),
                new DocxTextExtractor(),
                new PdfTextExtractor(),
            })
        {
        }

        public DocumentReader(IEnumerable<ITextExtractor> extractors)
        {
            _byExtension = new Dictionary<string, ITextExtractor>(StringComparer.OrdinalIgnoreCase);
            foreach (var extractor in extractors)
            {
                foreach (var ext in extractor.Extensions)
                    _byExtension[ext] = extractor;
            }

            _fallback = new PlainTextExtractor();
        }

        /// <summary>File extensions that have a dedicated (non-fallback) extractor.</summary>
        public IEnumerable<string> SupportedExtensions => _byExtension.Keys.OrderBy(k => k);

        public string Read(string filePath)
        {
            if (!File.Exists(filePath))
                throw new DocumentReadException($"File not found: '{filePath}'.");

            string extension = Path.GetExtension(filePath);
            var extractor = _byExtension.TryGetValue(extension, out var found) ? found : _fallback;

            try
            {
                return extractor.Extract(filePath);
            }
            catch (DocumentReadException)
            {
                throw;
            }
            catch (Exception ex)
            {
                string kind = string.IsNullOrEmpty(extension) ? "file" : $"{extension} file";
                throw new DocumentReadException(
                    $"Could not read {kind} '{filePath}': {ex.Message}", ex);
            }
        }
    }
}
