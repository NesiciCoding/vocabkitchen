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
                        profilerType = args[++i].ToLowerInvariant();
                        break;
                    case "--file":
                        filePath = args[++i];
                        break;
                    case "--text":
                        text = args[++i];
                        break;
                    default:
                        text ??= args[i];
                        break;
                }
            }

            if (filePath != null)
                text = File.ReadAllText(filePath);

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
