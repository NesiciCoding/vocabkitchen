using System.Linq;
using System.Text;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

namespace VkProfilerCli.TextExtraction
{
    /// <summary>
    /// Extracts the visible paragraph text from a Word (.docx) document using the
    /// Open XML SDK. One paragraph per line; tabs preserved as spaces.
    /// </summary>
    public class DocxTextExtractor : ITextExtractor
    {
        public string[] Extensions => new[] { ".docx" };

        public string Extract(string filePath)
        {
            using var document = WordprocessingDocument.Open(filePath, false);
            var body = document.MainDocumentPart?.Document?.Body;
            if (body == null)
                return string.Empty;

            var sb = new StringBuilder();
            foreach (var paragraph in body.Descendants<Paragraph>())
            {
                foreach (var element in paragraph.Descendants())
                {
                    switch (element)
                    {
                        case Text text:
                            sb.Append(text.Text);
                            break;
                        case TabChar:
                            sb.Append(' ');
                            break;
                        case Break:
                            sb.Append('\n');
                            break;
                    }
                }
                sb.Append('\n');
            }

            return sb.ToString();
        }
    }
}
