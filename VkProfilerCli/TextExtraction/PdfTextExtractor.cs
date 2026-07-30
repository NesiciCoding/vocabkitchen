using System.Text;
using UglyToad.PdfPig;
using UglyToad.PdfPig.Content;
using UglyToad.PdfPig.DocumentLayoutAnalysis.TextExtractor;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Extracts text from a PDF using PdfPig. Uses <see cref="ContentOrderTextExtractor"/>
    /// so words come out in reading order rather than raw content-stream order (which can
    /// jumble multi-column or complex layouts). Note: image-only / scanned PDFs contain no
    /// text layer and yield an empty result (no OCR is performed).
    /// </summary>
    public class PdfTextExtractor : ITextExtractor
    {
        public string[] Extensions => new[] { ".pdf" };

        public string Extract(string filePath)
        {
            var sb = new StringBuilder();
            using var pdf = PdfDocument.Open(filePath);
            foreach (Page page in pdf.GetPages())
            {
                sb.AppendLine(ContentOrderTextExtractor.GetText(page));
            }

            return sb.ToString();
        }
    }
}
