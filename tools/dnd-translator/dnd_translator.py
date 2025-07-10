#!/usr/bin/env python3
"""
D&D Translation CLI Tool
Translates D&D-related content using OpenAI models with context awareness
Specifically designed for translating base.json to language-specific JSON files
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import re

try:
    from openai import OpenAI
except ImportError:
    logging.error("Required libraries not installed. Please run: pip install openai")
    sys.exit(1)


# Constants
DEFAULT_MODEL = "gpt-4-turbo-preview"
DEFAULT_BATCH_SIZE = 50
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 4000
RECENT_BATCH_WEIGHT = 0.7
OLDER_BATCH_WEIGHT = 0.3
RATE_LIMIT_DELAY = 1
COST_CONFIRMATION_THRESHOLD = 5.0
MAX_RETRIES = 3
RETRY_DELAY = 2
RETRY_BACKOFF_MULTIPLIER = 2

# D&D-specific system prompt
SYSTEM_PROMPT = """You are a professional translator specializing in Dungeons & Dragons content. 
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



@dataclass
class TranslationConfig:
    """Configuration for translation operations"""
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    batch_size: int = DEFAULT_BATCH_SIZE
    rate_limit_delay: float = RATE_LIMIT_DELAY
    cost_confirmation_threshold: float = COST_CONFIRMATION_THRESHOLD
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    retry_backoff_multiplier: float = RETRY_BACKOFF_MULTIPLIER
    

class TranslationError(Exception):
    """Base exception for translation errors"""
    pass


class APIError(TranslationError):
    """OpenAI API related errors"""
    pass


class FileProcessingError(TranslationError):
    """File processing related errors"""
    pass


class ValidationError(TranslationError):
    """Input validation errors"""
    pass


class DnDTranslator:
    """Handles D&D-specific translations using OpenAI"""
    
    def __init__(self, config: Optional[TranslationConfig] = None, api_key: Optional[str] = None):
        self.config = config or TranslationConfig()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValidationError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass via --api-key")
        
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise APIError(f"Failed to initialize OpenAI client: {e}")
        
        # Timing tracking for predictions
        self.batch_times = []
        self.start_time = None
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def predict_remaining_time(self, completed_batches: int, remaining_batches: int) -> str:
        """Predict remaining time based on completed batch times"""
        if len(self.batch_times) == 0:
            return "Calculating..."
        
        # Use adaptive average - more weight to recent batches
        if len(self.batch_times) <= 3:
            # Use simple average for first few batches
            avg_time = sum(self.batch_times) / len(self.batch_times)
        else:
            # Weighted average favoring recent batches
            recent_batches = self.batch_times[-3:]
            older_batches = self.batch_times[:-3]
            
            recent_avg = sum(recent_batches) / len(recent_batches)
            older_avg = sum(older_batches) / len(older_batches) if older_batches else recent_avg
            
            avg_time = (recent_avg * RECENT_BATCH_WEIGHT) + (older_avg * OLDER_BATCH_WEIGHT)
        
        # Predict remaining time
        estimated_seconds = avg_time * remaining_batches
        
        # Format time duration
        if estimated_seconds < 60:
            return f"{estimated_seconds:.0f}s"
        elif estimated_seconds < 3600:
            minutes = estimated_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = estimated_seconds / 3600
            return f"{hours:.1f}h"
    
    def format_elapsed_time(self, start_time: float) -> str:
        """Format elapsed time since start"""
        elapsed = time.time() - start_time
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        elif elapsed < 3600:
            return f"{elapsed/60:.1f}m"
        else:
            return f"{elapsed/3600:.1f}h"
    
    def translate_batch(self, texts: List[str], target_language: str, source_language: str = "English") -> Dict[str, str]:
        """Translate a batch of texts with D&D context and retry logic"""
        # Create a mapping of lowercased keys to original texts for translation
        batch_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
        
        prompt = f"""Translate the following D&D content from {source_language} to {target_language}. 
Return ONLY the translations in the same numbered format, nothing else:

{batch_text}"""
        
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
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
                last_exception = e
                self.logger.warning(f"Translation attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.config.max_retries - 1:
                    # Wait before retrying with exponential backoff
                    delay = self.config.retry_delay * (self.config.retry_backoff_multiplier ** attempt)
                    self.logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All {self.config.max_retries} translation attempts failed")
        
        # If we get here, all retries failed
        raise APIError(f"Translation failed after {self.config.max_retries} attempts: {str(last_exception)}")
    
    def translate_json_file(self, input_file: Path, output_file: Path, target_language: str, 
                          batch_size: int = 50, source_language: str = "English", 
                          language_code: str = None, start_line: int = None, end_line: int = None, 
                          skip_existing: bool = False) -> None:
        """Translate a JSON array file in batches"""
        # Input validation
        if not input_file.exists():
            raise ValidationError(f"Input file does not exist: {input_file}")
        
        if not target_language.strip():
            raise ValidationError("Target language cannot be empty")
        
        if batch_size <= 0:
            raise ValidationError("Batch size must be positive")
        
        if start_line is not None and start_line <= 0:
            raise ValidationError("Start line must be positive")
        
        if end_line is not None and end_line <= 0:
            raise ValidationError("End line must be positive")
        
        if start_line is not None and end_line is not None and start_line > end_line:
            raise ValidationError("Start line must be less than or equal to end line")
        
        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValidationError("Input file must contain a JSON array")
            
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
                raise ValidationError(f"Invalid range: start_line {start_line} must be less than end_line {end_line}")
            
            # Slice the data
            if start_line or end_line:
                data = data[start_idx:end_idx]
                self.logger.info(f"Processing lines {start_idx + 1} to {end_idx} ({len(data)} entries)")
            
            self.logger.info(f"Loaded {len(data)} entries from {input_file}")
            
            # Generate output filename with -ai suffix if not provided
            if not output_file:
                if language_code:
                    # Use provided language code (e.g., "de-de")
                    output_name = f"{language_code}-ai.json"
                else:
                    # Generate from target language (e.g., "German" -> "de-de-ai.json")
                    lang_code = target_language[:2].lower()
                    output_name = f"{lang_code}-{lang_code}-ai.json"
                
                output_file = input_file.parent / output_name
            
            # Load existing translations if skip_existing is enabled
            existing_translations = {}
            if skip_existing and output_file.exists():
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        existing_translations = json.load(f)
                    self.logger.info(f"Loaded {len(existing_translations)} existing translations from {output_file}")
                except Exception as e:
                    self.logger.warning(f"Could not load existing translations: {e}")
            
            # Filter out already translated entries
            if skip_existing and existing_translations:
                original_count = len(data)
                data = [entry for entry in data if entry.lower() not in existing_translations]
                skipped_count = original_count - len(data)
                self.logger.info(f"Skipped {skipped_count} already translated entries")
                
                if len(data) == 0:
                    self.logger.info("All entries already translated!")
                    return
            
            # Process in batches
            all_translations = existing_translations.copy()  # Start with existing translations
            total_batches = (len(data) + batch_size - 1) // batch_size
            
            # Initialize timing
            self.start_time = time.time()
            self.logger.info(f"Starting translation of {len(data)} entries in {total_batches} batches...")
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                remaining_batches = total_batches - batch_num
                
                # Start timing this batch
                batch_start = time.time()
                
                # Show progress with time estimates
                elapsed = self.format_elapsed_time(self.start_time)
                eta = self.predict_remaining_time(batch_num - 1, remaining_batches + 1)
                self.logger.info(f"Batch {batch_num}/{total_batches} ({len(batch)} items) | Elapsed: {elapsed} | ETA: {eta}")
                
                try:
                    translations = self.translate_batch(batch, target_language, source_language)
                    all_translations.update(translations)
                    
                    # Record batch time (excluding the rate limit delay)
                    batch_time = time.time() - batch_start
                    self.batch_times.append(batch_time)
                    
                    # Show completion status for this batch
                    self.logger.info(f"  ✓ Completed in {batch_time:.1f}s")
                    
                    # Add a small delay to avoid rate limiting
                    if batch_num < total_batches:
                        time.sleep(self.config.rate_limit_delay)
                        
                except Exception as e:
                    self.logger.error(f"  ✗ Error: {e}")
                    self.logger.info("  Continuing with next batch...")
                    continue
            
            # Save translations
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_translations, f, ensure_ascii=False, indent=2)
            
            # Final timing summary
            total_time = time.time() - self.start_time
            successful_batches = len(self.batch_times)
            avg_batch_time = sum(self.batch_times) / len(self.batch_times) if self.batch_times else 0
            
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"TRANSLATION COMPLETE!")
            self.logger.info(f"{'='*50}")
            self.logger.info(f"Total time: {self.format_elapsed_time(self.start_time)}")
            self.logger.info(f"Successful batches: {successful_batches}/{total_batches}")
            self.logger.info(f"Average batch time: {avg_batch_time:.1f}s")
            new_translations = len(all_translations) - len(existing_translations)
            self.logger.info(f"Translated {new_translations} new entries")
            self.logger.info(f"Total entries in output: {len(all_translations)}")
            self.logger.info(f"Saved to: {output_file}")
            
            if successful_batches > 0:
                entries_per_second = new_translations / total_time
                self.logger.info(f"Translation rate: {entries_per_second:.1f} entries/second")
            self.logger.info(f"{'='*50}")
            
        except Exception as e:
            self.logger.error(f"Failed to process file: {str(e)}")
            raise FileProcessingError(f"Failed to process file: {str(e)}")


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
  
  # Resume translation, skipping already translated entries
  %(prog)s -i base.json -l German --skip-existing
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
    parser.add_argument("--skip-existing", action="store_true", help="Skip entries that are already translated")
    parser.add_argument("--model", default="gpt-4-turbo-preview", help="OpenAI model to use")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    
    args = parser.parse_args()
    
    try:
        # Create configuration
        config = TranslationConfig(model=args.model)
        
        # Initialize translator
        translator = DnDTranslator(config=config, api_key=args.api_key)
        
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
            end_line=args.end_line,
            skip_existing=args.skip_existing
        )
    
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()