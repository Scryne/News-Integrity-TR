/**
 * Saved-DOM fixtures for x-dom.ts (x-dom-extraction rule 8).
 *
 * SYNTHETIC: hand-built to mirror the X markup the S1 DOM-anchor spike read on
 * 2026-07-19/20 (article[data-testid=tweet], User-Name, tweetText, the
 * "<rest_id>-follow" button, socialContext, the quote block, the profile header
 * follow button and followers link). They pin the extractor's contract; they
 * are not a capture of today's x.com. Replace with real saved fragments when
 * the extractor is next touched on a live page.
 */

const author = (name: string, handle: string, postId: string, datetime: string) => `
  <div data-testid="User-Name">
    <a href="/${handle}" role="link"><span>${name}</span></a>
    <a href="/${handle}" role="link"><span>@${handle}</span></a>
    <span>·</span>
    <a href="/${handle}/status/${postId}" role="link"><time datetime="${datetime}">3s</time></a>
  </div>`;

const followButton = (restId: string, handle: string, following = false) =>
  `<button data-testid="${restId}-${following ? "unfollow" : "follow"}" aria-label="${following ? "Takibi bırak" : "Takip et"} @${handle}"><span>Takip et</span></button>`;

/** Timeline row: no inline follow anchor (S1: 4/4 absent on home timeline). */
export const timeline = `
<article data-testid="tweet">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111111", "2026-07-14T18:03:00.000Z")}
  <div data-testid="tweetText"><span>Son dakika: köprüde trafik durdu</span></div>
</article>`;

/** Permalink of an account the viewer does not follow: inline anchor present. */
export const permalink = `
<article data-testid="tweet">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111111", "2026-07-14T18:03:00.000Z")}
  ${followButton("1234567890123456789", "gundemhaber")}
  <div data-testid="tweetText"><span>Son dakika: köprüde trafik durdu</span></div>
</article>`;

/** A follow button for someone else (e.g. a mentioned account) must be ignored. */
export const permalinkWrongAnchor = `
<article data-testid="tweet">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111111", "2026-07-14T18:03:00.000Z")}
  ${followButton("44196397", "baskahesap")}
  <div data-testid="tweetText"><span>@baskahesap dedi ki</span></div>
</article>`;

/** Quote post: the embedded post has its own User-Name, time and text. */
export const quoted = `
<article data-testid="tweet">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111122", "2026-07-15T08:00:00.000Z")}
  ${followButton("1234567890123456789", "gundemhaber")}
  <div data-testid="tweetText"><span>Bakın ne demiş</span></div>
  <div role="link" tabindex="0">
    <div data-testid="User-Name">
      <span>Kaynak Hesap</span><span>@kaynakhesap</span><time datetime="2026-07-01T10:00:00.000Z">1 Tem</time>
    </div>
    <div data-testid="tweetText"><span>orijinal iddia</span></div>
  </div>
</article>`;

/** Reply: "Replying to @x" line outside the text, author line and quote. */
export const reply = `
<article data-testid="tweet">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111133", "2026-07-16T09:30:00.000Z")}
  ${followButton("1234567890123456789", "gundemhaber")}
  <div><span>Yanıt olarak: </span><a href="/hedefhesap" role="link">@hedefhesap</a></div>
  <div data-testid="tweetText"><span>Yanlış bilgi, <a href="/ucuncuhesap">@ucuncuhesap</a> da gördü</span></div>
</article>`;

/** Repost row: the article is the original post; socialContext names the reposter. */
export const repost = `
<article data-testid="tweet">
  <div><a href="/reposthesabi" role="link"><span data-testid="socialContext">Repost Hesabı yeniden yayınladı</span></a></div>
  ${author("Gündem Haber", "gundemhaber", "1811111111111111144", "2026-07-17T11:00:00.000Z")}
  <div data-testid="tweetText"><span>Asıl gönderi</span></div>
</article>`;

/** Author's profile page: header follow button (followed account) + exact follower count. */
export const profileHeader = (count: string) => `
<div data-testid="UserName"><span>@gundemhaber</span></div>
${followButton("1234567890123456789", "gundemhaber", true)}
<a href="/gundemhaber/verified_followers"><span>${count}</span> <span>Takipçi</span></a>
${timeline}`;
