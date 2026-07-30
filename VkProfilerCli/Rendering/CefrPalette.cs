using System.Collections.Generic;
using Spectre.Console;

namespace VkProfilerCli.Rendering
{
    /// <summary>
    /// Maps CEFR levels (and the profiler CSS classes) to the colours the original
    /// Vocabkitchen web app used, so the terminal view matches the site.
    /// </summary>
    public static class CefrPalette
    {
        /// <summary>CEFR levels in ascending difficulty, followed by the off-list bucket.</summary>
        public static readonly string[] OrderedLevels = { "A1", "A2", "B1", "B2", "C1", "C2", "Off List" };

        private static readonly Dictionary<string, string> LevelHex = new()
        {
            ["A1"] = "0099CC",
            ["A2"] = "00BB00",
            ["B1"] = "FF9900",
            ["B2"] = "B30000",
            ["C1"] = "D733FF",
            ["C2"] = "DB7093",
            ["Off List"] = "888888",
        };

        // The profiler tags each word span with one of these CSS classes.
        private static readonly Dictionary<string, string> CssClassToLevel = new()
        {
            ["profilerA1Word"] = "A1",
            ["profilerA2Word"] = "A2",
            ["profilerB1Word"] = "B1",
            ["profilerB2Word"] = "B2",
            ["profilerC1Word"] = "C1",
            ["profilerC2Word"] = "C2",
            ["profilerOffList"] = "Off List",
        };

        public static Color ColorForLevel(string level) =>
            LevelHex.TryGetValue(level, out var hex) ? HexToColor(hex) : Color.Default;

        public static string HexForLevel(string level) =>
            LevelHex.TryGetValue(level, out var hex) ? hex : null;

        /// <summary>Resolve a paragraph span's CSS class to its CEFR level (null if unknown).</summary>
        public static string LevelForCssClass(string cssClass)
        {
            if (string.IsNullOrEmpty(cssClass))
                return null;

            // Row spans carry "word profilerXxWord"; paragraph spans carry just the level class.
            foreach (var pair in CssClassToLevel)
            {
                if (cssClass.Contains(pair.Key))
                    return pair.Value;
            }

            return null;
        }

        private static Color HexToColor(string hex)
        {
            byte r = System.Convert.ToByte(hex.Substring(0, 2), 16);
            byte g = System.Convert.ToByte(hex.Substring(2, 2), 16);
            byte b = System.Convert.ToByte(hex.Substring(4, 2), 16);
            return new Color(r, g, b);
        }
    }
}
