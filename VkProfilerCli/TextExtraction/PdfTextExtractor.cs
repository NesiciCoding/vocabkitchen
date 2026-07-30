using System.Text;
using UglyToad.PdfPig;
using UglyToad.PdfPig.Content;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Extracts text from a PDF using PdfPig. Note: image-only / scanned PDFs contain
    /// no text layer and yield an empty result (no OCR is performed).
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
                sb.AppendLine(page.Text);
            }

            return sb.ToString();
        }
    }
}
