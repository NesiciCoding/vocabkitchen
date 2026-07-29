using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using VkCore.Models.Profiler;
using VkInfrastructure.Profilers;

namespace VkProfilerCli
{
    public class Program
    {
        public static int Main(string[] args)
        {
            string profilerType = "all";
            string text = null;
            string filePath = null;

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--type":
                        if (!TryTakeValue(args, ref i, "--type", out profilerType))
                            return 1;
                        profilerType = profilerType.ToLowerInvariant();
                        break;
                    case "--file":
                        if (!TryTakeValue(args, ref i, "--file", out filePath))
                            return 1;
                        break;
                    case "--text":
                        if (!TryTakeValue(args, ref i, "--text", out text))
                            return 1;
                        break;
                    default:
                        text ??= args[i];
                        break;
                }
            }

            if (filePath != null)
            {
                try
                {
                    text = File.ReadAllText(filePath);
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                {
                    Console.Error.WriteLine($"Could not read file '{filePath}': {ex.Message}");
                    return 1;
                }
            }

            if (text == null && Console.IsInputRedirected)
                text = Console.In.ReadToEnd();

            if (string.IsNullOrWhiteSpace(text))
            {
                Console.Error.WriteLine("Usage: vkprofiler [--type cefr|awl|nawl|all] [--text \"...\" | --file path.txt | < stdin]");
                return 1;
            }

            var profilers = new Dictionary<string, VkCore.Interfaces.IProfiler>
            {
                ["cefr"] = new CefrProfiler(),
                ["awl"] = new AwlProfiler(),
                ["nawl"] = new NawlProfiler(),
            };

            var typesToRun = profilerType == "all"
                ? profilers.Keys
                : profilerType.Split(',').Select(t => t.Trim());

            var output = new Dictionary<string, object>();
            int? totalWordCount = null;

            foreach (var type in typesToRun)
            {
                if (!profilers.TryGetValue(type, out var profiler))
                {
                    Console.Error.WriteLine($"Unknown profiler type '{type}'. Valid types: cefr, awl, nawl, all.");
                    return 1;
                }

                ProfilerResult result = profiler.Profile(text);
                totalWordCount ??= result.TotalWordCount;

                var levels = new Dictionary<string, object>();
                foreach (var kvp in result.TableResult)
                {
                    levels[kvp.Key] = new
                    {
                        percentage = kvp.Value.Percentage,
                        wordCount = kvp.Value.Rows?.Sum(r => r.Occurrences) ?? 0,
                        words = kvp.Value.Rows?
                            .OrderByDescending(r => r.Occurrences)
                            .Select(r => new { word = StripHtml(r.RowHtml), occurrences = r.Occurrences })
                    };
                }

                output[type] = levels;
            }

            var final = new
            {
                totalWordCount,
                results = output
            };

            var json = JsonSerializer.Serialize(final, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            Console.WriteLine(json);
            return 0;
        }

        private static bool TryTakeValue(string[] args, ref int i, string flag, out string value)
        {
            if (i + 1 >= args.Length)
            {
                Console.Error.WriteLine($"Missing value for {flag}.");
                value = null;
                return false;
            }

            value = args[++i];
            return true;
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
