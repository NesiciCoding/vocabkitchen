using System.Collections.Generic;
using System.Linq;
using VkCore.Models.Profiler;

namespace VkProfilerCli.Rendering
{
    /// <summary>One CEFR band's tally within a profiled text.</summary>
    public readonly struct LevelStat
    {
        public string Level { get; }
        public int WordCount { get; }
        public double Percentage { get; }   // share of all counted words, 0..100

        public LevelStat(string level, int wordCount, double percentage)
        {
            Level = level;
            WordCount = wordCount;
            Percentage = percentage;
        }
    }

    /// <summary>
    /// Derives display-ready statistics and a headline verdict from a CEFR
    /// <see cref="ProfilerResult"/>.
    /// </summary>
    public class CefrStats
    {
        public int TotalWordCount { get; }
        public IReadOnlyList<LevelStat> Levels { get; }

        /// <summary>The band that most recognised words sit in (the "typical" difficulty).</summary>
        public string TypicalLevel { get; }

        /// <summary>The band you need to know to cover ~90% of recognised words.</summary>
        public string CoverageLevel { get; }

        /// <summary>Human-readable summary combining the two measures.</summary>
        public string VerdictDescription { get; }

        private const double CoverageTarget = 0.90; // band at which 90% of classified words are covered

        public CefrStats(ProfilerResult result)
        {
            TotalWordCount = result.TotalWordCount;

            var levels = new List<LevelStat>();
            foreach (var level in CefrPalette.OrderedLevels)
            {
                int count = 0;
                if (result.TableResult.TryGetValue(level, out var table) && table.Rows != null)
                    count = table.Rows.Sum(r => r.Occurrences);

                double pct = TotalWordCount > 0 ? count * 100.0 / TotalWordCount : 0;
                levels.Add(new LevelStat(level, count, pct));
            }

            Levels = levels;
            (TypicalLevel, CoverageLevel, VerdictDescription) = ComputeVerdict(levels);
        }

        private static (string typical, string coverage, string description) ComputeVerdict(List<LevelStat> levels)
        {
            // Order matters (A1..C2) for the cumulative-coverage walk.
            var cefrBands = levels.Where(l => l.Level != "Off List").ToList();
            int classified = cefrBands.Sum(l => l.WordCount);

            if (classified == 0)
                return ("—", "—", "No recognised vocabulary to profile.");

            // "Typical" = the single band holding the most recognised words.
            string typical = cefrBands
                .OrderByDescending(b => b.WordCount)
                .ThenBy(b => System.Array.IndexOf(CefrPalette.OrderedLevels, b.Level))
                .First().Level;

            // "Coverage" = lowest band at which cumulative coverage reaches the target.
            int cumulative = 0;
            string coverage = cefrBands.Last(b => b.WordCount > 0).Level;
            foreach (var band in cefrBands)
            {
                cumulative += band.WordCount;
                if (cumulative >= classified * CoverageTarget)
                {
                    coverage = band.Level;
                    break;
                }
            }

            string description = typical == coverage
                ? $"Most recognised words are {typical}."
                : $"Most words are {typical}; you need {coverage} to cover ~90%.";

            return (typical, coverage, description);
        }
    }
}
