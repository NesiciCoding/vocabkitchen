using System.Collections.Generic;
using System.Net;
using System.Text.RegularExpressions;

namespace VkProfilerCli.Rendering
{
    /// <summary>A run of text from the profiler's paragraph HTML and the CEFR level it belongs to.</summary>
    public readonly struct TextToken
    {
        /// <summary>The (entity-decoded) text.</summary>
        public string Text { get; }

        /// <summary>CEFR level (A1..C2, "Off List") for word runs; null for punctuation/whitespace.</summary>
        public string Level { get; }

        /// <summary>True when this token is a hard line break.</summary>
        public bool IsLineBreak { get; }

        public TextToken(string text, string level, bool isLineBreak = false)
        {
            Text = text;
            Level = level;
            IsLineBreak = isLineBreak;
        }
    }

    /// <summary>
    /// Parses the profiler's <c>ParagraphHtml</c> (word <c>&lt;span&gt;</c>s, <c>&lt;br /&gt;</c>
    /// line breaks, and HTML-entity punctuation) into a flat, ordered token stream that the
    /// terminal renderer can colour.
    /// </summary>
    public static class HtmlSpanParser
    {
        private static readonly Regex TokenRegex = new(
            @"<span class='(?<class>[^']*)'>(?<text>.*?)</span>|(?<br><br\s*/?>)",
            RegexOptions.Compiled | RegexOptions.Singleline);

        public static IReadOnlyList<TextToken> Parse(string paragraphHtml)
        {
            var tokens = new List<TextToken>();
            if (string.IsNullOrEmpty(paragraphHtml))
                return tokens;

            int lastIndex = 0;
            foreach (Match match in TokenRegex.Matches(paragraphHtml))
            {
                if (match.Index > lastIndex)
                    AddLiteral(tokens, paragraphHtml.Substring(lastIndex, match.Index - lastIndex));

                if (match.Groups["br"].Success)
                {
                    tokens.Add(new TextToken("\n", null, isLineBreak: true));
                }
                else
                {
                    string cssClass = match.Groups["class"].Value;
                    string text = WebUtility.HtmlDecode(match.Groups["text"].Value);
                    tokens.Add(new TextToken(text, CefrPalette.LevelForCssClass(cssClass)));
                }

                lastIndex = match.Index + match.Length;
            }

            if (lastIndex < paragraphHtml.Length)
                AddLiteral(tokens, paragraphHtml.Substring(lastIndex));

            return tokens;
        }

        private static void AddLiteral(List<TextToken> tokens, string raw)
        {
            string text = WebUtility.HtmlDecode(raw);
            if (text.Length > 0)
                tokens.Add(new TextToken(text, null));
        }
    }
}
