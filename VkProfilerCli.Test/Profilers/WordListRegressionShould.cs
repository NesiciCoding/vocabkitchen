using System.Linq;
using VkCore.Interfaces;
using VkCore.Models.Profiler;
using VkInfrastructure.Profilers;
using Xunit;

namespace VkProfilerCli.Test.Profilers
{
    // Regression guard for the curated word-list data. The lists were rebuilt from
    // public sources and validated against a dictionary; these tests assert that the
    // classes of noise CodeRabbit flagged (proper names, abbreviations, misspellings,
    // and over-generated non-words) are NOT classified as vocabulary, and that real
    // vocabulary still is. They run the real profilers against the shipped .txt lists.
    public class WordListRegressionShould
    {
        // Returns the single bucket ("A1".."C2"/"Awl"/"Nawl"/"Off List") a lone word
        // lands in. Profiling one word puts it in exactly one bucket.
        private static string BucketOf(IProfiler profiler, string word)
        {
            ProfilerResult result = profiler.Profile(word);
            return result.TableResult
                .Where(kv => (kv.Value.Rows?.Sum(r => r.Occurrences) ?? 0) > 0)
                .Select(kv => kv.Key)
                .SingleOrDefault();
        }

        [Theory]
        // proper names
        [InlineData("aaron")]
        [InlineData("aaronic")]
        [InlineData("angeles")]
        // corpus artifacts / non-words
        [InlineData("adda")]
        [InlineData("addy")]
        // misspellings
        [InlineData("accessability")]
        [InlineData("compatable")]
        [InlineData("residental")]
        [InlineData("writter")]
        // abbreviations / specialist terms
        [InlineData("kg")]
        [InlineData("iterator")]
        public void ClassifyCefrNoiseAsOffList(string junk)
        {
            Assert.Equal("Off List", BucketOf(new CefrProfiler(), junk));
        }

        [Theory]
        [InlineData("the")]
        [InlineData("and")]
        [InlineData("water")]
        [InlineData("cat")]
        public void ClassifyCommonWordsAsA1(string word)
        {
            Assert.Equal("A1", BucketOf(new CefrProfiler(), word));
        }

        [Theory]
        [InlineData("photosynthesis")]
        [InlineData("chlorophyll")]
        [InlineData("synthesize")]
        public void ClassifyRealAcademicWordsSomewhere(string word)
        {
            // We don't pin the exact CEFR band (data may shift), only that a real
            // word is recognised rather than dropped to Off List.
            Assert.NotEqual("Off List", BucketOf(new CefrProfiler(), word));
        }

        [Theory]
        // over-generated non-words that the naive inflation used to emit
        [InlineData("absorptioned")]
        [InlineData("accuracying")]
        [InlineData("accuratelying")]
        public void ExcludeNawlOverGeneratedNonWords(string nonWord)
        {
            Assert.Equal("Off List", BucketOf(new NawlProfiler(), nonWord));
        }

        [Theory]
        [InlineData("absorb")]
        [InlineData("absorption")]
        [InlineData("accelerate")]
        public void KeepRealNawlForms(string word)
        {
            Assert.Equal("Nawl", BucketOf(new NawlProfiler(), word));
        }

        [Fact]
        public void FixAwlAcknowledgementTypo()
        {
            // the corrected form is present in the AWL list...
            Assert.Equal("Awl", BucketOf(new AwlProfiler(), "acknowledgements"));
            // ...and the extraction typo is gone.
            Assert.Equal("Off List", BucketOf(new AwlProfiler(), "acknowledgemens"));
        }

        [Theory]
        [InlineData("significant")]
        [InlineData("analysis")]
        [InlineData("approach")]
        public void ClassifyAcademicWordsAsAwl(string word)
        {
            Assert.Equal("Awl", BucketOf(new AwlProfiler(), word));
        }
    }
}
