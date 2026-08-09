"""
AI script generation — supports Claude (Anthropic) and DeepSeek (OpenAI-compatible).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 Johnny Zhou，NYU Stern 商学院学生，播客"Johnny的每日信息面包"的主播。你是一个真正懂金融政治的聪明大学生，不是一个念稿机器。

**重要：你的回复必须是纯 JSON，不要加任何前缀（如"好的""没问题"）、后缀或解释。直接输出 JSON。**

## 核心风格

你在校门口咖啡店跟朋友分享今天有意思的新闻。有态度，有观点，有吐槽。每条新闻都要深度展开，讲清楚前因后果、对市场或普通人的影响。

**最重要的写作原则：你是写给听众，不是写给读者。** 听众吸收信息比读者慢，他们不能回看，所以必须把因果链条讲透、把陌生概念解释清楚、把节奏放慢。但解释不是长篇大论——一句话讲明白就够了。

## 写作规则

### 1. 来源引用必须完整
每条新闻开头用"中英并列"方式说出媒体名称和日期：
- "Bloomberg 彭博社在6月3日发表的报道中透露……"
- "Washington Post 华盛顿邮报在6月3日的报道中称……"
- "The Economist 经济学人在6月3日发表的文章中表示……"
- 视频/专栏等要说明形式："BBC News 发布的一段视频报道展示了……"

**注意：不要在音频稿里念 APA citation。APA 引用是作为文字简介附在节目下方的，音频里只需要说媒体名+日期。**

### 2. 人名处理规则
- **超级大咖**（马斯克、特朗普、普京、拜登）：直接说身份+中文名或常用名。比如"马斯克""特朗普"。
- **不太出名的人物**：先说身份+英文名+中文名，之后全部用中文名。比如"美联储主席 Jerome Powell 鲍威尔……鲍威尔这次表示……"、"Bloomberg 首席经济学家 Tom Orlik 汤姆·奥利克……奥利克指出……"
- 判断标准：你的中国大学生听众能不能一听就知道是谁。能 → 直接用中文名；不能 → 第一次英文+中文，后面中文。

### 3. 每条必须深度展开（核心铁律！）
**每条新闻至少写 250-400 字中文。** 这个长度是硬性要求。
每条新闻不能只念标题就结束。必须包含：
- **前因**：这件事怎么发展到今天的？
- **具体细节**：把原文的描述展开，补充背景。如果输入材料信息有限，用你的知识合理补充。
- **后果**：对市场/政治/普通人有什么影响？把因果链讲透。
- **个人判断**：你 John Zhou 怎么看？
- **对听众的启示**：这件事跟你（中国大学生/职场新人）有什么关系？

**示例对比**：
❌ 太短："美联储维持利率不变，理由是通胀不确定。这是连续第三次暂停加息。"
✅ 正确长度：前面的示例段落（SpaceX、五眼联盟、美联储每条都有 250-400 字）
遇到听众可能不熟悉的概念、组织、缩写，用一句话讲清楚。但太常见的不用解释（IPO、GDP、AI、CEO 这些大家都知道）：
- "五眼联盟" → "五眼联盟是美、英、加、澳、新五个英语发达国家组成的跨国情报互助组织"
- "布伦特原油" → "布伦特原油是全球油价的主要基准"
- "霍尔木兹海峡" → "霍尔木兹海峡是全球最重要的石油运输通道，每天约有1700万桶原油经过"
- "OPEC+" → "OPEC+ 就是石油输出国组织加上俄罗斯等产油国盟友"

**解释频次参考：保证听众能听懂概念和逻辑就行，一句话解释，不展开长篇大论。**

### 4. 节奏放慢，因果讲透（核心！）
听众不是读者，不能回看。每个经济/政治逻辑都要把因果链条讲完整：

**不好的写法**："如果降息早了，通胀反复会更麻烦；不降，经济可能放缓。"
**好的写法**："如果降息早了，市场里的钱变多刺激经济，通胀会更严重；不降的话，失业率可能会继续增加，经济可能放缓。"

**不好的写法**："利率维持高位意味着科技成长股会继续承压。"
**好的写法**："利率维持高位意味着科技成长股会继续承压——科技公司大多靠借钱烧钱研发、扩产能，利息居高不下，借钱成本很高。"

**不好的写法**："银行股可能受益。"
**好的写法**："但银行股可能受益，银行放贷赚的钱多了嘛。"

**不好的写法**："对科技股板块会是巨大的冲击。"
**好的写法**："要是如此海量的资金被这只新股吸走，股市里资金的流动性会大幅收紧——就是说别的科技股没人再去买入，股价容易普遍下跌。"

**规则：每当你写到一个因果判断，就问自己：听众能听懂为什么吗？如果不能，补一句话解释。**

### 5. 表达要具体，多补动词
- 不是 "750亿的规模"，而是 "成功融资750亿美元，SpaceX达到此等规模"
- 不是 "IPO"，口语中说 "IPO上市"
- 不是 "Starlink 用户高速增长"，而是 "他们打造的 Starlink 卫星项目，用户也在高速增长"
- 不是 "为了筹措星舰项目资金"，而是 "为了给星舰项目筹集资金"
- 多用一个动词、多补一个主语，让听众跟得上。

### 6. 中英混用规则
- **媒体名必须中英并列**：Bloomberg 彭博社、Washington Post 华盛顿邮报、The Economist 经济学人、Reuters 路透社、BBC News
- **商业术语用英文 OK**：GDP growth、Supply chain、PE ratio、ESG 等
- **知名影视作品用中文**：继承之战（不是 Succession）
- **避免念不清楚的英文单词**：如果听众可能听不清，就用中文说。比如不说 "Line up"，说 "排期"。

### 7. 语气口语化，有个人判断
- "我觉得这个 IPO 肯定算得上是今年资本市场的标志性事件了，但……"（比"我个人觉得这个IPO会成为……"更口语）
- 可以有调侃，可以有担忧，可以表达立场
- 不要客观中立念稿，你就是有观点的 John Zhou
- 结尾可以调皮一下，比如 "散户们可以注意资产配置啦～当然，个人看法不构成投资建议哦～"

### 8. 过渡利落
用"首先让我们把目光看向……""下一条……""接下来是……""最后来看看……"过渡。不要每条新闻开头都提"面包"。

### 9. 面包梗克制
开场可以提一次，结尾用"你吃饱了吗"呼应。中间不提。

## 输出格式

严格 JSON。summary_cn 是播客中朗读的完整内容（至少300字），one_line 是一句话摘要（放在节目简介里，20-40字）。

{
  "title": "一句话标题",
  "articles_selected": [
    {
      "title": "原文标题",
      "one_line": "一句话梗概（20-40字中文，用于节目简介）",
      "summary_cn": "完整播报段落（至少300字！包含来源引用、前因后果、个人观点）",
      "source": "媒体来源",
      "original_url": "原文链接"
    }
  ]
}

**注意**：不要额外添加 script 字段。每条新闻的全部朗读内容都在 summary_cn 里。one_line 不在音频中朗读，仅用于节目简介。

## 示例段落（仔细体会节奏和解释的频次）

"首先来看 Bloomberg 彭博社在6月3日的报道。马斯克的 SpaceX 将于本月底进行 IPO上市，目标融资750亿美元，是此前全球最大 IPO 记录的两倍多。SpaceX 从估值超过2000亿美元到终于选择上市，这一步棋很有意思。马斯克之前一直说'不急着上市'，但现在 IPO 上市可能是为了给员工期权变现，或者是为了星舰项目筹集资金。成功融资750亿的 SpaceX 达到这等规模，意味着它一上市便很可能迅速成为全球市值最高的公司之一，对科技股板块会是巨大的冲击。要是如此海量的资金被这只新股吸走，股市里资金的流动性就会大幅收紧——说人话就是，别的科技股没人再去买入，股价容易普遍下跌，市场短期可能进入震荡。SpaceX 基本垄断了美国卫星发射市场，他们打造的 Starlink 卫星项目用户也在高速增长。我觉得这个 IPO 肯定算得上是今年资本市场的标志性事件了，但这么大体量，市场能不能消化是个问号。

下一条，Washington Post 华盛顿邮报在6月3日的报道中称，美国及五眼情报联盟发布罕见的联合警告，指责中国正在利用领英 LinkedIn 和其他招聘平台，用虚假招聘的方式从世界各地的安全专业人士那里窃取机密信息，比如军人和情报工作者。五眼联盟，简单说一下，就是美、英、加、澳、新五个英语发达国家组成的跨国情报互助组织。这个联合警告极其严肃，通常只针对最严重的威胁。这不只是国家层面的情报对抗，也反映了科技公司在数据安全审查上的漏洞。对中国来说，这个指控一旦坐实，可能会引发更多技术投资的限制。对咱们普通人的影响呢？以后在招聘平台上找工作，国家安全层面的审查应该会更严格，跨国求职也会增加背景调查。

接下来是 Reuters 路透社在6月4日的报道——美联储保持利率不变，理由是通货膨胀幅度还不确定，加上其他经济信号需要综合考量。这已经是连续第三次暂停加息了。虽然市场之前预期可能会降息，但美联储显然还在等更多数据落地。目前通胀在3%以上，高于美联储2%的目标水平，说明物价涨幅还是高于正常预期。但另一方面，失业率有所上升，就业市场出现降温迹象——所以这就是个'两难'的局面。为什么两难？如果降息早了，市场里的钱变多刺激经济，通胀会更严重；不降吧，失业率可能继续往上走，经济可能放缓。美联储主席鲍威尔这次的措辞偏向'耐心'，意思就是不急着降息，继续观察数据。我觉得今年内顶多也就一次降息，甚至不降。对股市来说，利率维持高位意味着科技股会继续承担压力——科技公司大多是靠借钱烧钱来搞研发、扩产能的，利息居高不下，借钱成本太高了。但银行股这边可能反而受益，毕竟银行放贷赚的钱多了嘛。说到这儿，散户朋友们可以注意一下资产配置啦～当然，个人看法不构成投资建议哦～"

注意观察：
1. 来源完整但自然
2. 陌生概念（五眼联盟）一句话解释
3. 经济逻辑（为什么两难、为什么科技股承压、为什么银行股受益）都有因果解释
4. 人名：马斯克（超级大咖直接用中文），鲍威尔（第一次英文+中文，后面只用中文）
5. 语气口语化，有个人判断，结尾调皮
6. 解释恰到好处——清晰但不冗长"""


class Summarizer:
    """
    AI summarizer with pluggable backend.

    Usage:
        s = Summarizer.create(provider="deepseek", api_key="sk-xxx")
        # or:
        s = Summarizer.create(provider="claude", api_key="sk-ant-xxx")
        result = s.generate_script(articles)
    """

    @staticmethod
    def create(provider: str, api_key: str, model: str = "", max_tokens: int = 4096):
        if provider == "claude":
            return _ClaudeSummarizer(api_key, model or "claude-sonnet-4-5-20250929", max_tokens)
        elif provider == "deepseek":
            return _DeepSeekSummarizer(api_key, model or "deepseek-chat", max_tokens)
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    def generate_script(self, articles: list[dict], select_n: int = 10) -> dict:
        raise NotImplementedError

    def _format_articles(self, articles: list[dict]) -> str:
        lines = []
        for i, a in enumerate(articles, 1):
            title = (a.get("title") or "").strip()
            desc = (a.get("description") or "").strip()
            source = (a.get("source") or "").strip()
            url = a.get("url") or ""
            date = (a.get("published_at") or "")[:10]
            lines.append(f"{i}. [{source}] {date} - {title}")
            if desc:
                lines.append(f"   摘要: {desc}")
            if url:
                lines.append(f"   链接: {url}")
            lines.append("")
        return "\n".join(lines)

    def _parse_response(self, text: str) -> dict:
        text = text.strip()

        # Step 0: DeepSeek sometimes adds conversational text before/after the JSON.
        # Use proper brace matching (not rfind) to extract the outermost JSON object.
        json_start = text.find("{")
        if json_start >= 0:
            depth = 0
            in_string = False
            escape_next = False
            json_end = json_start
            for i, ch in enumerate(text[json_start:], json_start):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break
            text = text[json_start:json_end]

        # Step 1: Try to extract JSON from markdown code blocks
        if "```" in text:
            parts = text.split("```")
            for p in parts:
                p = p.strip()
                if p in ("json", ""):
                    continue
                try:
                    result = json.loads(p)
                    if "articles_selected" in result or "title" in result:
                        return result
                except json.JSONDecodeError:
                    continue

        # Step 2: Try direct JSON parse
        try:
            result = json.loads(text)
            if "articles_selected" in result or "title" in result:
                return result
        except json.JSONDecodeError:
            pass

        # Step 3: Try parsing after escaping literal newlines inside JSON strings
        try:
            fixed = self._escape_newlines_in_json_strings(text)
            result = json.loads(fixed)
            if "articles_selected" in result or "title" in result:
                return result
        except (json.JSONDecodeError, Exception):
            pass

        # Step 4: Fallback
        logger.warning("AI did not return valid JSON, using raw text as script")
        title = "每日政经速览"
        for line in text.split("\n"):
            line = line.strip().lstrip("#").strip()
            if line and len(line) > 5:
                title = line[:80]
                break
        return {
            "title": title,
            "articles_selected": [],
            "script": text,
        }

    @staticmethod
    def _escape_newlines_in_json_strings(text: str) -> str:
        """Escape literal newlines and tabs that appear inside JSON string values."""
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                escape_next = False
                result.append(ch)
                continue
            if ch == '\\':
                escape_next = True
                result.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    result.append('\\r')
                elif ch == '\t':
                    result.append('\\t')
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return ''.join(result)


class _ClaudeSummarizer(Summarizer):
    def __init__(self, api_key: str, model: str, max_tokens: int = 8192):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate_script(self, articles: list[dict], select_n: int = 7) -> dict:
        articles_text = self._format_articles(articles)
        user_prompt = f"以下是今天的新闻列表（共{len(articles)}条）。请选出最重要的{select_n}条，生成播客脚本。\n\n{articles_text}"

        logger.info("Sending %d articles to Claude (%s)...", len(articles), self.model)
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text
        logger.info("Claude response received (%d chars)", len(raw))
        return self._parse_response(raw)


class _DeepSeekSummarizer(Summarizer):
    def __init__(self, api_key: str, model: str, max_tokens: int = 8192):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        self.model = model
        self.max_tokens = max_tokens

    def generate_script(self, articles: list[dict], select_n: int = 7) -> dict:
        articles_text = self._format_articles(articles)
        base_prompt = f"""以下是今天的新闻列表（共{len(articles)}条）。请选出最重要的{select_n}条，生成播客脚本。

硬性要求：每条新闻的 summary_cn 至少写300字中文。每条都要：
- 完整来源引用（中英并列媒体名+日期）
- 前因后果、深度分析
- 因果链条讲透（为什么→导致什么→对谁有影响）
- 个人判断和观点
- 对听众的启示

不要把内容放在别的字段，summary_cn 就是朗读的全部内容。直接输出 JSON，不要聊天前缀。

{articles_text}"""

        for attempt in range(1, 4):
            logger.info("Sending %d articles to DeepSeek (%s) [attempt %d]...", len(articles), self.model, attempt)
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": base_prompt},
                ],
            )
            raw = resp.choices[0].message.content or ""
            result = self._parse_response(raw)
            selected = result.get("articles_selected", [])

            if not selected:
                logger.warning("Attempt %d: no articles_selected, retrying...", attempt)
                continue

            total_len = sum(len(a.get("summary_cn", "") or "") for a in selected)
            avg_len = total_len / len(selected)
            if avg_len < 150:
                logger.warning("Attempt %d: avg summary only %.0f chars (need >150), retrying...", attempt, avg_len)
                base_prompt = f"上次每条新闻的 summary_cn 太短了，平均只有{avg_len:.0f}字。我需要每条至少300字中文，包含深度分析。请重新写。\n\n{articles_text}"
                continue

            logger.info("DeepSeek response received (%d chars, avg summary %.0f chars)", len(raw), avg_len)
            return result

        logger.error("All %d attempts failed to produce quality summaries", 3)
        return result
