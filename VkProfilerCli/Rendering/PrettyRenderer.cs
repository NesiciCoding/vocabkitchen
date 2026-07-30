using System.Collections.Generic;
using System.Linq;
using Spectre.Console;
using Spectre.Console.Rendering;
using VkCore.Models.Profiler;

namespace VkProfilerCli.Rendering
{
    /// <summary>
    /// Renders a colour-coded, human-friendly view of the profiler results to a terminal:
    /// a CEFR distribution summary, per-level word lists, and the source text tinted by level.
    /// </summary>
    public class PrettyRenderer
    {
        private const int MaxWordsPerLevel = 40;
        private readonly IAnsiConsole _console;

        public PrettyRenderer(IAnsiConsole console)
        {
            _console = console;
        }

        public void Render(string sourceLabel, IReadOnlyDictionary<string, ProfilerResult> resultsByType)
        {
            _console.Write(new Rule("[bold]Vocabulary Profile[/]").LeftJustified());
            if (!string.IsNullOrEmpty(sourceLabel))
                _console.MarkupLine($"[grey]Source:[/] {Markup.Escape(sourceLabel)}");
            _console.WriteLine();

            if (resultsByType.TryGetValue("cefr", out var cefr))
                RenderCefr(cefr);

            foreach (var type in new[] { "awl", "nawl" })
            {
                if (resultsByType.TryGetValue(type, out var result))
                    RenderBinaryProfiler(type.ToUpperInvariant(), result);
            }
        }

        private void RenderCefr(ProfilerResult result)
        {
            var stats = new CefrStats(result);

            // 1. Distribution summary --------------------------------------------------
            var summary = new Grid();
            summary.AddColumn();
            summary.AddRow($"[bold]Total words:[/] {stats.TotalWordCount}");
            summary.AddRow(
                $"[bold]Typical:[/] [{HexMarkup(stats.TypicalLevel)}]{Markup.Escape(stats.TypicalLevel)}[/]" +
                $"   [bold]90% coverage:[/] [{HexMarkup(stats.CoverageLevel)}]{Markup.Escape(stats.CoverageLevel)}[/]");
            summary.AddRow($"[grey]{Markup.Escape(stats.VerdictDescription)}[/]");

            _console.Write(new Panel(summary)
                .Header("[bold]Summary[/]")
                .Border(BoxBorder.Rounded)
                .Expand());

            var chart = new BreakdownChart()
                .Width(64)
                .ShowPercentage()
                .UseValueFormatter(v => $"{v:0}%");
            foreach (var level in stats.Levels.Where(l => l.WordCount > 0))
                chart.AddItem(level.Level, level.Percentage, CefrPalette.ColorForLevel(level.Level));

            _console.WriteLine();
            _console.Write(chart);
            _console.WriteLine();

            // 2. Per-level word lists --------------------------------------------------
            var panels = new List<IRenderable>();
            foreach (var level in CefrPalette.OrderedLevels)
            {
                if (!result.TableResult.TryGetValue(level, out var table) || table.Rows == null || table.Rows.Count == 0)
                    continue;

                panels.Add(BuildLevelPanel(level, table));
            }

            if (panels.Count > 0)
                _console.Write(new Columns(panels).Collapse());

            // 3. Colour-highlighted text ----------------------------------------------
            _console.WriteLine();
            RenderHighlightedText(result.ParagraphHtml);
        }

        private IRenderable BuildLevelPanel(string level, ProfilerTableResult table)
        {
            string hex = HexMarkup(level);
            var ordered = table.Rows
                .OrderByDescending(r => r.Occurrences)
                .ThenBy(r => StripHtml(r.RowHtml));

            var lines = new List<string>();
            int maxPlain = 0;
            foreach (var row in ordered.Take(MaxWordsPerLevel))
            {
                string plainWord = StripHtml(row.RowHtml);
                string count = row.Occurrences > 1 ? $" ×{row.Occurrences}" : string.Empty;
                maxPlain = System.Math.Max(maxPlain, plainWord.Length + count.Length);

                string countMarkup = row.Occurrences > 1 ? $" [grey]×{row.Occurrences}[/]" : string.Empty;
                lines.Add($"[{hex}]{Markup.Escape(plainWord)}[/]{countMarkup}");
            }

            int remaining = table.Rows.Count - MaxWordsPerLevel;
            if (remaining > 0)
            {
                string more = $"+{remaining} more";
                maxPlain = System.Math.Max(maxPlain, more.Length);
                lines.Add($"[grey]{more}[/]");
            }

            // Ensure the panel is at least wide enough for its header (level + percentage),
            // so short single-word columns (e.g. Off List) don't clip the header label.
            string headerPlain = $"{level}  {table.Percentage}";
            int contentWidth = System.Math.Max(maxPlain, headerPlain.Length);

            var body = new Markup(string.Join("\n", lines));
            var panel = new Panel(body)
                .Header($"[{hex}]{level}[/]  [grey]{Markup.Escape(table.Percentage)}[/]")
                .Border(BoxBorder.Rounded)
                .Padding(1, 0, 1, 0);
            panel.Width = contentWidth + 4;
            return panel;
        }

        private void RenderHighlightedText(string paragraphHtml)
        {
            var tokens = HtmlSpanParser.Parse(paragraphHtml);
            if (tokens.Count == 0)
                return;

            var markup = new System.Text.StringBuilder();
            foreach (var token in tokens)
            {
                if (token.IsLineBreak)
                {
                    markup.Append('\n');
                    continue;
                }

                string escaped = Markup.Escape(token.Text);
                if (token.Level != null)
                    markup.Append($"[{HexMarkup(token.Level)}]{escaped}[/]");
                else
                    markup.Append(escaped);
            }

            _console.Write(new Panel(new Markup(markup.ToString()))
                .Header("[bold]Text[/]")
                .Border(BoxBorder.Rounded)
                .Expand());
        }

        private void RenderBinaryProfiler(string title, ProfilerResult result)
        {
            _console.WriteLine();
            var rows = new List<string>();
            foreach (var kvp in result.TableResult)
            {
                if (kvp.Value.Rows == null || kvp.Value.Rows.Count == 0)
                    continue;

                int count = kvp.Value.Rows.Sum(r => r.Occurrences);
                rows.Add($"[bold]{Markup.Escape(kvp.Key)}[/]  [grey]{Markup.Escape(kvp.Value.Percentage)} ({count})[/]");

                string words = string.Join(", ", kvp.Value.Rows
                    .OrderByDescending(r => r.Occurrences)
                    .Take(MaxWordsPerLevel)
                    .Select(r => Markup.Escape(StripHtml(r.RowHtml))));
                if (words.Length > 0)
                    rows.Add($"[grey]{words}[/]");
            }

            var body = new Markup(rows.Count > 0 ? string.Join("\n", rows) : "[grey]No matches.[/]");
            _console.Write(new Panel(body)
                .Header($"[bold]{Markup.Escape(title)}[/] — academic vocabulary")
                .Border(BoxBorder.Rounded)
                .Expand());
        }

        private static string HexMarkup(string level)
        {
            string hex = CefrPalette.HexForLevel(level);
            return hex != null ? "#" + hex : "default";
        }

        private static string StripHtml(string rowHtml)
        {
            if (string.IsNullOrEmpty(rowHtml))
                return rowHtml;

            int gt = rowHtml.IndexOf('>');
            int lt = rowHtml.LastIndexOf('<');
            if (gt >= 0 && lt > gt)
                return rowHtml.Substring(gt + 1, lt - gt - 1);

            return rowHtml;
        }
    }
}
