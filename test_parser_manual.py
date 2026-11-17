from modules.crawler.parser import PageParser

html = """
<html>
<head>
    <title>Test Page</title>
    <meta name="robots" content="noindex, nofollow">
</head>
<body>
    <h1>Test Heading</h1>
    <a href="/page1">A</a>
    <a href="/page1">B</a>
    <a href="https://example.com">C</a>
    <a href="https://example.com" rel="nofollow">D</a>
</body>
</html>
"""

result = PageParser.parse(html, "https://example.com/")

print("\n========== PARSER TEST ==========")

for key in [
    "title",
    "is_indexable",
    "is_nofollow",
    "internal_links_count",
    "unique_internal_links_count",
    "external_links_count",
    "unique_external_links_count",
    "nofollow_links_count",
    "content_hash"
]:
    print(f"{key}: {result[key]}")

print("\n========== TEST COMPLETED ==========")
