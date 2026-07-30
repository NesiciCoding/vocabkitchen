using System.Linq;
using VkProfilerCli.Rendering;
using Xunit;

namespace VkProfilerCli.Test.Rendering
{
    public class HtmlSpanParserShould
    {
        [Fact]
        public void Tag_word_spans_with_their_cefr_level()
        {
            var tokens = HtmlSpanParser.Parse("<span class='profilerA1Word'>cat</span>");
            var token = Assert.Single(tokens);
            Assert.Equal("cat", token.Text);
            Assert.Equal("A1", token.Level);
        }

        [Fact]
        public void Map_off_list_class_to_off_list_level()
        {
            var tokens = HtmlSpanParser.Parse("<span class='profilerOffList'>chlorophyll</span>");
            Assert.Equal("Off List", tokens.Single().Level);
        }

        [Fact]
        public void Decode_entities_in_punctuation_between_words()
        {
            var tokens = HtmlSpanParser.Parse("<span class='profilerA1Word'>he</span>&#39;s");
            Assert.Equal("he", tokens[0].Text);
            Assert.Null(tokens[1].Level);
            Assert.Equal("'s", tokens[1].Text);
        }

        [Fact]
        public void Emit_line_breaks_as_break_tokens()
        {
            var tokens = HtmlSpanParser.Parse("<span class='profilerA1Word'>a</span><br /><span class='profilerA1Word'>b</span>");
            Assert.True(tokens[1].IsLineBreak);
            Assert.Equal("\n", tokens[1].Text);
        }

        [Fact]
        public void Return_empty_for_null_or_empty_input()
        {
            Assert.Empty(HtmlSpanParser.Parse(null));
            Assert.Empty(HtmlSpanParser.Parse(""));
        }
    }
}
