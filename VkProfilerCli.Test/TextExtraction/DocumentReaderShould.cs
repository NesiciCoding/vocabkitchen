using System;
using System.IO;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using UglyToad.PdfPig.Fonts.Standard14Fonts;
using UglyToad.PdfPig.Writer;
using VkProfilerCli.TextExtraction;
using Xunit;

namespace VkProfilerCli.Test.TextExtraction
{
    public class DocumentReaderShould : IDisposable
    {
        private readonly string _dir;
        private readonly DocumentReader _reader = new();

        public DocumentReaderShould()
        {
            _dir = Path.Combine(Path.GetTempPath(), "vkprofiler-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_dir);
        }

        public void Dispose()
        {
            try { Directory.Delete(_dir, recursive: true); } catch { /* best effort */ }
        }

        private string Write(string name, string content)
        {
            string path = Path.Combine(_dir, name);
            File.WriteAllText(path, content);
            return path;
        }

        [Fact]
        public void Read_plain_text_verbatim()
        {
            string path = Write("sample.txt", "The cat sat on the mat.");
            Assert.Equal("The cat sat on the mat.", _reader.Read(path));
        }

        [Fact]
        public void Fall_back_to_plain_text_for_unknown_extensions()
        {
            string path = Write("notes.log", "plain content");
            Assert.Equal("plain content", _reader.Read(path));
        }

        [Fact]
        public void Strip_markdown_syntax()
        {
            string path = Write("doc.md", "# Heading\n\nSome **bold** and a [link](https://example.com) plus `code`.");
            string text = _reader.Read(path);

            Assert.Contains("Heading", text);
            Assert.Contains("bold", text);
            Assert.Contains("link", text);
            Assert.DoesNotContain("**", text);
            Assert.DoesNotContain("#", text);
            Assert.DoesNotContain("https://example.com", text);
        }

        [Fact]
        public void Extract_text_from_docx()
        {
            string path = Path.Combine(_dir, "doc.docx");
            CreateDocx(path, "First paragraph.", "Second paragraph.");

            string text = _reader.Read(path);

            Assert.Contains("First paragraph.", text);
            Assert.Contains("Second paragraph.", text);
        }

        [Fact]
        public void Extract_text_from_pdf()
        {
            string path = Path.Combine(_dir, "doc.pdf");
            CreatePdf(path, "Hello from a PDF document.");

            string text = _reader.Read(path);

            Assert.Contains("Hello", text);
            Assert.Contains("PDF", text);
        }

        [Fact]
        public void Extract_multi_fragment_pdf_as_separated_words_in_order()
        {
            string path = Path.Combine(_dir, "multi.pdf");
            // Two separate text fragments on one line; the higher-level extractor keeps
            // them as distinct, ordered words rather than mashing them into one token.
            var builder = new PdfDocumentBuilder();
            var font = builder.AddStandard14Font(Standard14Font.Helvetica);
            var page = builder.AddPage(595, 842);
            page.AddText("alpha", 12, new UglyToad.PdfPig.Core.PdfPoint(50, 750), font);
            page.AddText("omega", 12, new UglyToad.PdfPig.Core.PdfPoint(300, 750), font);
            File.WriteAllBytes(path, builder.Build());

            string text = _reader.Read(path);

            Assert.Contains("alpha", text);
            Assert.Contains("omega", text);
            Assert.True(text.IndexOf("alpha") < text.IndexOf("omega"),
                $"Expected alpha before omega, got: {text}");
        }

        [Fact]
        public void Throw_when_file_has_no_analysable_text()
        {
            string path = Write("empty.txt", "   \n\t ");
            var ex = Assert.Throws<DocumentReadException>(() => _reader.Read(path));
            Assert.Contains("No analysable text", ex.Message);
        }

        [Fact]
        public void Throw_for_missing_file()
        {
            string path = Path.Combine(_dir, "nope.txt");
            var ex = Assert.Throws<DocumentReadException>(() => _reader.Read(path));
            Assert.Contains("not found", ex.Message, StringComparison.OrdinalIgnoreCase);
        }

        [Fact]
        public void Wrap_corrupt_docx_in_document_read_exception()
        {
            string path = Path.Combine(_dir, "broken.docx");
            File.WriteAllText(path, "this is not a real docx");
            Assert.Throws<DocumentReadException>(() => _reader.Read(path));
        }

        private static void CreateDocx(string path, params string[] paragraphs)
        {
            using var doc = WordprocessingDocument.Create(path, WordprocessingDocumentType.Document);
            var main = doc.AddMainDocumentPart();
            main.Document = new Document(new Body());
            var body = main.Document.Body;
            foreach (var p in paragraphs)
                body.AppendChild(new Paragraph(new Run(new Text(p))));
            main.Document.Save();
        }

        private static void CreatePdf(string path, string content)
        {
            var builder = new PdfDocumentBuilder();
            var font = builder.AddStandard14Font(Standard14Font.Helvetica);
            var page = builder.AddPage(595, 842);
            page.AddText(content, 12, new UglyToad.PdfPig.Core.PdfPoint(50, 750), font);
            File.WriteAllBytes(path, builder.Build());
        }
    }
}
