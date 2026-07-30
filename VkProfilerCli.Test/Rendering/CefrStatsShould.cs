using System.Collections.Generic;
using System.Linq;
using VkCore.Models.Profiler;
using VkProfilerCli.Rendering;
using Xunit;

namespace VkProfilerCli.Test.Rendering
{
    public class CefrStatsShould
    {
        private static ProfilerResult ResultWith(params (string level, int count)[] levels)
        {
            var result = new ProfilerResult { TotalWordCount = levels.Sum(l => l.count) };
            foreach (var (level, count) in levels)
            {
                result.TableResult[level] = new ProfilerTableResult
                {
                    Percentage = "0%",
                    Rows = count > 0
                        ? new List<ProfilerTableRow> { new() { Occurrences = count, RowHtml = $"<span>{level}word</span>" } }
                        : new List<ProfilerTableRow>()
                };
            }
            return result;
        }

        [Fact]
        public void Total_word_count_is_carried_through()
        {
            var stats = new CefrStats(ResultWith(("A1", 3), ("A2", 1)));
            Assert.Equal(4, stats.TotalWordCount);
        }

        [Fact]
        public void Compute_per_level_percentages_of_total()
        {
            var stats = new CefrStats(ResultWith(("A1", 3), ("B1", 1)));
            var a1 = stats.Levels.Single(l => l.Level == "A1");
            Assert.Equal(75, a1.Percentage, 3);
        }

        [Fact]
        public void Coverage_level_is_lowest_band_covering_ninety_percent()
        {
            // 50% A1 + 50% B1 -> A1 alone is only 50%, need up to B1 to clear 90%.
            var stats = new CefrStats(ResultWith(("A1", 50), ("B1", 50)));
            Assert.Equal("B1", stats.CoverageLevel);
        }

        [Fact]
        public void Typical_level_is_the_band_with_the_most_words()
        {
            // Most words are A1, but enough C2 words that 90% coverage still needs C2.
            var stats = new CefrStats(ResultWith(("A1", 80), ("C2", 20)));
            Assert.Equal("A1", stats.TypicalLevel);
            Assert.Equal("C2", stats.CoverageLevel);
        }

        [Fact]
        public void Off_list_words_do_not_count_toward_the_verdict()
        {
            // All classified vocabulary is A1; a pile of off-list words must not shift the verdict.
            var stats = new CefrStats(ResultWith(("A1", 10), ("Off List", 90)));
            Assert.Equal("A1", stats.TypicalLevel);
            Assert.Equal("A1", stats.CoverageLevel);
        }

        [Fact]
        public void Verdict_handles_no_recognised_vocabulary()
        {
            var stats = new CefrStats(ResultWith(("Off List", 5)));
            Assert.Equal("—", stats.TypicalLevel);
            Assert.Equal("—", stats.CoverageLevel);
        }
    }
}
