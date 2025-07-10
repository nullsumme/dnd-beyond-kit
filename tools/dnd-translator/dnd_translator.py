#!/usr/bin/env python3
"""
D&D Translation CLI Tool
Translates D&D-related content using OpenAI models with context awareness
Specifically designed for translating base.json to language-specific JSON files
"""

import argparse
import json
import os
import sys
import time
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import re

try:
    from openai import OpenAI
except ImportError:
    print("Error: OpenAI library not installed. Please run: pip install openai")
    sys.exit(1)


class DnDTranslator:
    """Handles D&D-specific translations using OpenAI"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass via --api-key")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        
        # D&D-specific context
        self.system_prompt = """You are a professional translator specializing in Dungeons & Dragons content. 
        When translating:
        - Maintain consistency with official D&D terminology in the target language
        - Preserve game mechanics terms (AC, HP, DC, etc.) when they're commonly used untranslated
        - Keep proper nouns (character names, place names) unless there's an established translation
        - Maintain the fantasy tone and style appropriate for D&D content
        - Consider context: spell names, class features, monster abilities, and rule descriptions may require different approaches
        - Preserve any game notation like dice rolls (e.g., 1d20+5)
        - Be aware of D&D-specific concepts like alignment, spell schools, damage types, and conditions
        - Translate complete sentences naturally, don't translate word-by-word
        """
    
    def translate_batch(self, texts: List[str], target_language: str, source_language: str = "English") -> Dict[str, str]:
        """Translate a batch of texts with D&D context"""
        # Create a mapping of lowercased keys to original texts for translation
        batch_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
        
        prompt = f"""Translate the following D&D content from {source_language} to {target_language}. 
Return ONLY the translations in the same numbered format, nothing else:

{batch_text}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=4000
            )
            
            # Parse the response
            translated_text = response.choices[0].message.content.strip()
            translations = {}
            
            # Extract numbered translations
            lines = translated_text.split('\n')
            for line in lines:
                match = re.match(r'^(\d+)\.\s*(.+)$', line.strip())
                if match:
                    idx = int(match.group(1)) - 1
                    if idx < len(texts):
                        # Create key-value pair with lowercased key
                        key = texts[idx].lower()
                        value = match.group(2).strip()
                        translations[key] = value
            
            return translations
            
        except Exception as e:
            raise Exception(f"Translation failed: {str(e)}")
    
    def translate_json_file(self, input_file: Path, output_file: Path, target_language: str, 
                          batch_size: int = 50, source_language: str = "English", 
                          language_code: str = None, start_line: int = None, end_line: int = None) -> None:
        """Translate a JSON array file in batches"""
        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValueError("Input file must contain a JSON array")
            
            # Limit lines if specified
            total_entries = len(data)
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else total_entries
            
            # Validate indices
            if start_idx < 0:
                start_idx = 0
            if end_idx > total_entries:
                end_idx = total_entries
            if start_idx >= end_idx:
                raise ValueError(f"Invalid range: start_line {start_line} must be less than end_line {end_line}")
            
            # Slice the data
            if start_line or end_line:
                data = data[start_idx:end_idx]
                print(f"Processing lines {start_idx + 1} to {end_idx} ({len(data)} entries)")
            
            print(f"Loaded {len(data)} entries from {input_file}")
            
            # Process in batches
            all_translations = {}
            total_batches = (len(data) + batch_size - 1) // batch_size
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)...")
                
                try:
                    translations = self.translate_batch(batch, target_language, source_language)
                    all_translations.update(translations)
                    
                    # Add a small delay to avoid rate limiting
                    if batch_num < total_batches:
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"Error in batch {batch_num}: {e}")
                    print("Continuing with next batch...")
                    continue
            
            # Generate output filename with -ai suffix
            if not output_file:
                if language_code:
                    # Use provided language code (e.g., "de-de")
                    output_name = f"{language_code}-ai.json"
                else:
                    # Generate from target language (e.g., "German" -> "de-de-ai.json")
                    lang_code = target_language[:2].lower()
                    output_name = f"{lang_code}-{lang_code}-ai.json"
                
                output_file = input_file.parent / output_name
            
            # Save translations
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_translations, f, ensure_ascii=False, indent=2)
            
            print(f"\nTranslation complete!")
            print(f"Translated {len(all_translations)} out of {len(data)} entries")
            print(f"Saved to: {output_file}")
            
        except Exception as e:
            raise Exception(f"Failed to process file: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="D&D Translation Tool - Translate base.json to language-specific JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate base.json to German
  %(prog)s -i translations/base.json -l German
  
  # Translate with custom batch size
  %(prog)s -i translations/base.json -l Spanish --batch-size 100
  
  # Specify output file and language code
  %(prog)s -i base.json -l French -o fr-fr-ai.json --lang-code fr-fr
  
  # Use a different model
  %(prog)s -i base.json -l Italian --model gpt-3.5-turbo
  
  # Translate lines 1-100 for testing
  %(prog)s -i base.json -l German --start-line 1 --end-line 100
  
  # Translate lines 500-1000
  %(prog)s -i base.json -l Spanish --start-line 500 --end-line 1000
        """
    )
    
    parser.add_argument("-i", "--input", required=True, help="Input base.json file")
    parser.add_argument("-l", "--language", required=True, help="Target language (e.g., German, Spanish)")
    parser.add_argument("-o", "--output", help="Output file (default: {lang-code}-ai.json)")
    parser.add_argument("--lang-code", help="Language code for output (e.g., de-de, es-es)")
    parser.add_argument("-s", "--source", default="English", help="Source language (default: English)")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of entries per batch (default: 50)")
    parser.add_argument("--start-line", type=int, help="Start line number (1-based, default: 1)")
    parser.add_argument("--end-line", type=int, help="End line number (inclusive, default: all)")
    parser.add_argument("--model", default="gpt-4-turbo-preview", help="OpenAI model to use")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    
    args = parser.parse_args()
    
    try:
        # Initialize translator
        translator = DnDTranslator(api_key=args.api_key, model=args.model)
        
        # Process the file
        input_path = Path(args.input)
        if not input_path.exists():
            parser.error(f"Input file not found: {args.input}")
        
        output_path = Path(args.output) if args.output else None
        
        translator.translate_json_file(
            input_path, 
            output_path, 
            args.language,
            batch_size=args.batch_size,
            source_language=args.source,
            language_code=args.lang_code,
            start_line=args.start_line,
            end_line=args.end_line
        )
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()