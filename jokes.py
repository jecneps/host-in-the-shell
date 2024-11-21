import os
import sys
import argparse
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from typing import List, Dict, Any, Optional
import random

class ComedyGenerator:
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.anthropic_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.hyperbolic_client = AsyncOpenAI(
            api_key=os.environ["HYPERBOLIC_API_KEY"],
            base_url="https://api.hyperbolic.xyz/v1"
        )
        
        self.models = {
            "gpt4": "gpt-4o",
            "gpt4_base": "gpt-4o",
            "claude": "claude-3-5-sonnet-20241022",
            "llama_base": "meta-llama/Meta-Llama-3.1-405B",
            "llama_instruct": "meta-llama/Meta-Llama-3.1-405B-Instruct"
        }

    def _encode_image(self, image_path: str) -> Optional[str]:
        """
        Read and encode a local image file to base64.
        Returns None if image cannot be read or processed.
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return None

    def _get_image_mime_type(self, image_path: str) -> str:
        """
        Determine MIME type based on file extension.
        """
        extension = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(extension, 'image/jpeg')  # default to jpeg if unknown

    async def reformat_transcript(self, transcript_text: str) -> str:
        prompt = Path('prompts/reformat_prompt.txt').read_text()
        response = await self.openai_client.chat.completions.create(
            model=self.models["gpt4_base"],
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript_text}
            ]
        )
        print(response.choices[0].message.content)
        return response.choices[0].message.content

    async def _generate_openai_joke(self, prompt: str, attempt: int, image_path: str = None) -> str:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": ""}
        ]

        if image_path:
            try:
                image_base64 = self._encode_image(image_path)
                if image_base64:
                    mime_type = self._get_image_mime_type(image_path)
                    data_url = f"data:{mime_type};base64,{image_base64}"
                    model = self.models["gpt4"]
                    messages = [
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}}
                        ]}
                    ]
                else:
                    model = self.models["gpt4_base"]
            except Exception as e:
                print(f"Error setting up OpenAI image message: {e}")
                model = self.models["gpt4_base"]
        else:
            model = self.models["gpt4_base"]

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000
        )
        print(response.choices[0].message.content)
        return f"GPT-4 - Try {attempt}:\n{response.choices[0].message.content}\n"

    async def _generate_claude_joke(self, prompt: str, attempt: int, image_path: str = None) -> str:
        if image_path:
            image_base64 = self._encode_image(image_path)
            
            if image_base64:
                mime_type = self._get_image_mime_type(image_path)
                message_content = [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64
                        }
                    }
                ]
            else:
                print(f"Failed to encode image {image_path}, proceeding with text-only prompt")
                message_content = prompt
        else:
            message_content = prompt

        response = await self.anthropic_client.messages.create(
            model=self.models["claude"],
            max_tokens=1000,
            messages=[{"role": "user", "content": message_content}]
        )
        print(response.content[0].text)
        return f"Claude - Try {attempt}:\n{response.content[0].text}\n"

    async def _generate_llama_joke(self, model: str, prompt: str, attempt: int, image_path: str = None) -> str:
        response = await self.hyperbolic_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        model_name = "Llama Base" if model == self.models["llama_base"] else "Llama Instruct"
        print(response.choices[0].message.content)
        return f"{model_name} - Try {attempt}:\n{response.choices[0].message.content}\n"

    async def generate_joke(self, formatted_jokes: str, task_type: str, topic: str = None, image_path: str = None) -> str:
        prompt = Path(f'prompts/{task_type}_prompt.txt').read_text().format(
            jokes=formatted_jokes,
            topic=topic if topic else ""
        )
        
        tasks: List[asyncio.Task] = []
        for attempt in range(1, 4):
            tasks.extend([
                asyncio.create_task(self._generate_openai_joke(prompt, attempt, image_path)),
                asyncio.create_task(self._generate_claude_joke(prompt, attempt, image_path)),
                # asyncio.create_task(self._generate_llama_joke(self.models["llama_base"], prompt, attempt)),
                # asyncio.create_task(self._generate_llama_joke(self.models["llama_instruct"], prompt, attempt))
            ])

        results = await asyncio.gather(*tasks)
        return f"Task Type: {task_type}\n" + "".join(results)

async def main(transcript_path: str = None, transcript_text: str = None, image_path: str = None):
    generator = ComedyGenerator()
    
    if transcript_path:
        transcript_text = Path(transcript_path).read_text()
    
    formatted_jokes = await generator.reformat_transcript(transcript_text)
    
    tasks = [
        generator.generate_joke(formatted_jokes, 'new_joke'),
        generator.generate_joke(formatted_jokes, 'topic_joke', topic='How do you teach a dog it is mortal?'),
        generator.generate_joke(formatted_jokes, 'image_caption', image_path=image_path),
        # generator.generate_joke(formatted_jokes, 'one_minute_set')
    ]
    
    results = await asyncio.gather(*tasks)
    
    output_path = f'output/{transcript_path if transcript_path else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}{random.randint(0,1000)}_output.txt'
    Path('output').mkdir(exist_ok=True)
    Path(output_path).write_text("\n\n".join(results))
    
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--transcript_path', type=str, help='Path to the transcript file')
    parser.add_argument('--transcript_text', type=str, help='Text of the transcript')
    parser.add_argument('--image_path', type=str, help='Path to local image file')
    args = parser.parse_args()
    
    asyncio.run(main(args.transcript_path, args.transcript_text, args.image_path))