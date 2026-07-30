using System.Collections.Generic;
using Spectre.Console.Testing;
using VkCore.Models.Profiler;
using VkInfrastructure.Profilers;
using VkProfilerCli.Rendering;
using Xunit;

namespace VkProfilerCli.Test.Rendering
{
    public class PrettyRendererShould
    {
        private static string Render(string text, params string[] types)
        {
            var results = new Dictionary<string, ProfilerResult>();
            foreach (var type in types)
            {
                results[type] = type switch
                {
                    "cefr" => new CefrProfiler().Profile(text),
                    "awl" => new AwlProfiler().Profile(text),
                    "nawl" => new NawlProfiler().Profile(text),
                    _ => null
                };
            }

            var console = new TestConsole();
            console.Profile.Width = 120;
            new PrettyRenderer(console).Render("sample.txt", results);
            return console.Output;
        }

        [Fact]
        public void Show_header_summary_and_source()
        {
            string output = Render("The cat sat on the mat.", "cefr");
            Assert.Contains("Vocabulary Profile", output);
            Assert.Contains("Summary", output);
            Assert.Contains("Typical", output);
            Assert.Contains("90% coverage", output);
            Assert.Contains("sample.txt", output);
        }

        [Fact]
        public void List_words_under_their_level_and_in_highlighted_text()
        {
            string output = Render("The cat sat on the mat.", "cefr");
            Assert.Contains("A1", output);
            Assert.Contains("cat", output);
        }

        [Fact]
        public void Render_academic_section_for_awl()
        {
            string output = Render("She analysed the philosophical implications of the data.", "cefr", "awl");
            Assert.Contains("AWL", output);
            Assert.Contains("academic vocabulary", output);
        }

        [Fact]
        public void Not_throw_on_empty_off_list_only_text()
        {
            string output = Render("qwertyuiop zxcvbnm", "cefr");
            Assert.Contains("Vocabulary Profile", output);
        }
    }
}
