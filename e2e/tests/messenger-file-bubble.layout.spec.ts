import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const conversationSource = readFileSync(
  new URL(
    "../../frontend/src/components/LeadMessenger/LeadConversation.vue",
    import.meta.url,
  ),
  "utf8",
);
const metadataSource = readFileSync(
  new URL(
    "../../frontend/src/components/LeadMessenger/MessageMetadata.vue",
    import.meta.url,
  ),
  "utf8",
);

const styles = `
	* { box-sizing: border-box; }
	body { margin: 0; font-family: sans-serif; }
	.message-row { display: flex; justify-content: flex-end; width: 100%; }
	.message-bubble {
		min-width: 0;
		width: fit-content;
		max-width: 94%;
		padding: 8px 12px;
	}
	.message-metadata {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
		margin-bottom: 4px;
		min-width: 100%;
		width: 0;
	}
	.message-labels {
		display: flex;
		min-width: 0;
		flex: 1 1 0%;
		flex-wrap: wrap;
		align-items: center;
		column-gap: 8px;
	}
	.badge {
		max-width: 100%;
		overflow: clip;
		white-space: nowrap;
	}
	.actions { width: 32px; flex-shrink: 0; }
	.attachment-renderer {
		display: grid;
		width: fit-content;
		max-width: 20rem;
		margin-top: 8px;
	}
	.attachment-card {
		display: flex;
		width: fit-content;
		min-width: 0;
		max-width: min(20rem, 100%);
		align-items: center;
		gap: 12px;
		padding: 12px;
	}
	.file-icon { width: 40px; height: 40px; flex-shrink: 0; }
	.file-copy { min-width: 0; }
	.file-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.external-icon { width: 16px; flex-shrink: 0; }
	@media (min-width: 640px) {
		.message-bubble { max-width: 78%; }
	}
`;

function bubble(provider: string, source: string, title: string) {
  return `<div class="message-row">
		<div class="message-bubble" data-provider="${provider}">
			<div class="message-metadata">
				<div class="message-labels"><span>Agent</span><span class="badge">${source}</span></div>
				<div class="actions">...</div>
			</div>
			<div class="attachment-renderer">
				<div class="attachment-card">
					<div class="file-icon"></div>
					<div class="file-copy"><div class="file-title">${title}</div><div>1 KB</div></div>
					<div class="external-icon"></div>
				</div>
			</div>
		</div>
	</div>`;
}

test("generic file-only bubbles are sized by the attachment in a real browser", async ({
  page,
}) => {
  expect(conversationSource).toContain(':constrain-intrinsic-width="');
  expect(conversationSource).toContain(
    "isGenericFileOnlyMessage(item.message)",
  );
  expect(metadataSource).toContain("? 'w-0 min-w-full' : 'min-w-0'");

  await page.setViewportSize({ width: 960, height: 720 });
  await page.setContent(`<style>${styles}</style>
		${bubble("telegram_bot", "Telegram - Support Operations Bot", "Проб.txt")}
		${bubble("max_direct", "MAX - Support Operations Bot", "Проб.txt")}
		${bubble("vk_direct", "VK - Support Operations Bot", "Проб.txt")}`);

  for (const provider of ["telegram_bot", "max_direct", "vk_direct"]) {
    const sizes = await page
      .locator(`[data-provider="${provider}"]`)
      .evaluate((element) => {
        const bubbleBounds = element.getBoundingClientRect();
        const rendererBounds = element
          .querySelector(".attachment-renderer")!
          .getBoundingClientRect();
        const metadataBounds = element
          .querySelector(".message-metadata")!
          .getBoundingClientRect();
        return {
          bubble: bubbleBounds.width,
          content: bubbleBounds.width - 24,
          renderer: rendererBounds.width,
          metadata: metadataBounds.width,
        };
      });

    expect(Math.abs(sizes.content - sizes.renderer)).toBeLessThanOrEqual(1);
    expect(Math.abs(sizes.content - sizes.metadata)).toBeLessThanOrEqual(1);
    expect(sizes.bubble).toBeLessThan(220);
  }
});

test("long generic filenames stay constrained and truncate on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await page.setContent(`<style>${styles}</style>
		${bubble(
      "telegram_bot",
      "Telegram - Support Operations Bot",
      "Очень-длинное-имя-документа-которое-не-должно-расширять-message-bubble.docx",
    )}`);

  const sizes = await page
    .locator('[data-provider="telegram_bot"]')
    .evaluate((element) => {
      const bubbleBounds = element.getBoundingClientRect();
      const title = element.querySelector(".file-title")!;
      return {
        bubble: bubbleBounds.width,
        titleClient: title.clientWidth,
        titleScroll: title.scrollWidth,
      };
    });

  expect(sizes.bubble).toBeLessThanOrEqual(360 * 0.94 + 1);
  expect(sizes.titleScroll).toBeGreaterThan(sizes.titleClient);
});
