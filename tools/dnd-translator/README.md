# D&D Translation Tool

A Python CLI tool for translating D&D-related content using OpenAI models. Specifically designed to translate the `base.json` file to language-specific JSON files with D&D context awareness.

## Features

- **D&D-Specific Context**: Maintains consistency with official D&D terminology
- **Batch Processing**: Handles large translation files efficiently
- **Rate Limiting**: Built-in delays to avoid API rate limits
- **Progress Tracking**: Shows translation progress with batch information
- **Dynamic Time Prediction**: Estimates completion time based on actual batch performance
- **Error Handling**: Continues processing even if individual batches fail
- **Flexible Output**: Configurable output filenames and language codes

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Alternative**: If you prefer using pipx:
```bash
brew install pipx  # Install pipx first
pipx install openai  # Install OpenAI library globally
```

## Usage

### Basic Usage

Translate `base.json` to German:
```bash
python3 dnd_translator.py -i ../../translations/base.json -l German
```

This will create a file named `ge-ge-ai.json` in the same directory as the input file.

### Advanced Usage

#### Specify Language Code and Output File
```bash
python3 dnd_translator.py -i ../../translations/base.json -l German --lang-code de-de -o de-de-ai.json
```

#### Custom Batch Size
```bash
python3 dnd_translator.py -i ../../translations/base.json -l Spanish --batch-size 100
```

#### Different OpenAI Model
```bash
python3 dnd_translator.py -i ../../translations/base.json -l French --model gpt-3.5-turbo
```

#### Specify API Key via Command Line
```bash
python3 dnd_translator.py -i ../../translations/base.json -l Italian --api-key your-api-key
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input base.json file path | Required |
| `-l, --language` | Target language (e.g., German, Spanish) | Required |
| `-o, --output` | Output file path | `{lang-code}-ai.json` |
| `--lang-code` | Language code for output (e.g., de-de, es-es) | Auto-generated |
| `-s, --source` | Source language | English |
| `--batch-size` | Number of entries per batch | 50 |
| `--start-line` | Start line number (1-based) | 1 |
| `--end-line` | End line number (inclusive) | All |
| `--skip-existing` | Skip entries that are already translated | False |
| `--model` | OpenAI model to use | gpt-4-turbo-preview |
| `--api-key` | OpenAI API key | From environment |

## Input/Output Format

### Input (base.json)
```json
[
  "A Backpack holds up to",
  "A Barbarian might discover latent magical ability",
  "A Bardic Inspiration die is expended when it's rolled"
]
```

### Output (e.g., de-de-ai.json)
```json
{
  "a backpack holds up to": "Ein Rucksack fasst bis zu",
  "a barbarian might discover latent magical ability": "Ein Barbar könnte eine latente magische Fähigkeit entdecken",
  "a bardic inspiration die is expended when it's rolled": "Ein bardischer Inspirationswürfel wird verbraucht, wenn er gewürfelt wird"
}
```

## Translation Quality

The tool is specifically designed for D&D content and:

- Maintains official D&D terminology consistency
- Preserves game mechanics terms (AC, HP, DC, etc.)
- Keeps proper nouns unless established translations exist
- Maintains fantasy tone and style
- Preserves dice notation (e.g., 1d20+5)
- Handles D&D-specific concepts correctly

## Error Handling

- Individual batch failures don't stop the entire process
- Progress is saved incrementally
- Clear error messages for debugging
- Continues with remaining batches on failures

## Examples

### Translate to German
```bash
python3 dnd_translator.py -i ../../translations/base.json -l German --lang-code de-de
```
Output: `de-de-ai.json`

### Translate to Spanish with larger batches
```bash
python3 dnd_translator.py -i ../../translations/base.json -l Spanish --lang-code es-es --batch-size 100
```
Output: `es-es-ai.json`

### Translate to French with custom output
```bash
python3 dnd_translator.py -i ../../translations/base.json -l French -o translations/fr-fr-ai.json
```
Output: `translations/fr-fr-ai.json`

### Translate lines 1-100 for testing
```bash
python3 dnd_translator.py -i ../../translations/base.json -l German --start-line 1 --end-line 100
```
Output: `ge-ge-ai.json` (with lines 1-100)

### Translate lines 500-1000
```bash
python3 dnd_translator.py -i ../../translations/base.json -l Spanish --start-line 500 --end-line 1000
```
Output: `es-es-ai.json` (with lines 500-1000)

### Resume translation, skipping already translated entries
```bash
python3 dnd_translator.py -i ../../translations/base.json -l German --skip-existing
```
Output: `ge-ge-ai.json` (only translates new entries, preserves existing ones)

## Tips

1. **Batch Size**: Start with smaller batches (25-50) for better error recovery
2. **Testing**: Use `--start-line 1 --end-line 100` to test with a small subset first
3. **API Limits**: The tool includes delays between batches to respect rate limits
4. **Cost**: Monitor your OpenAI usage as large translation files can be expensive
5. **Quality**: Review translations, especially for game-specific terms
6. **Resume**: Use `--skip-existing` to resume interrupted translations
7. **Incremental**: Perfect for adding new content to existing translations

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure `OPENAI_API_KEY` is set or use `--api-key`
2. **Rate Limiting**: Reduce batch size or add longer delays
3. **File Not Found**: Check input file path is correct
4. **Memory Issues**: Use smaller batch sizes for very large files

### Getting Help

```bash
python3 dnd_translator.py --help
```

## License

This tool is part of the DnD Beyond Kit project.