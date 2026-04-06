import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { ArrowLeft, CalendarDays, Search, ThumbsUp } from 'lucide-react'

import dataset from './data/articles.json'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type TextBlock = {
  type: 'text'
  text: string
}

type ImageBlock = {
  type: 'image'
  alt: string
  src: string
}

type Article = {
  id: number
  url: string
  sourceType: '回答' | '专栏' | '想法' | '其他'
  pageStart: number
  title: string
  likes: number
  date: string
  blocks: Array<TextBlock | ImageBlock>
  content: string
  excerpt: string
  imageCount: number
  hasImages: boolean
}

type Payload = {
  totalArticles: number
  totalImages: number
  articles: Article[]
}

type SortMode = 'likes' | 'date'

type Route =
  | {
      kind: 'home'
    }
  | {
      kind: 'article'
      id: number
    }

const payload = dataset as Payload

function formatLikes(likes: number) {
  return likes.toLocaleString('zh-CN')
}

function safeTitle(article: Article) {
  return article.title.trim() || `未命名条目 #${article.id}`
}

function articleHash(id: number) {
  return `#/article/${id}`
}

function homeHash() {
  return '#/'
}

function parseHash(hash: string): Route {
  const match = hash.match(/^#\/article\/(\d+)\/?$/)

  if (match) {
    return {
      kind: 'article',
      id: Number(match[1]),
    }
  }

  return { kind: 'home' }
}

function normalizeBlockText(text: string) {
  return text
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join(' ')
    .replace(/\s{2,}/g, ' ')
    .replace(/([\u4e00-\u9fff])\s+([\u4e00-\u9fff])/g, '$1$2')
    .replace(/([\u4e00-\u9fff])\s+([，。！？：；、])/g, '$1$2')
    .replace(/([，。！？：；、])\s+([\u4e00-\u9fff])/g, '$1$2')
}

function previewText(article: Article) {
  const preview = normalizeBlockText(article.excerpt || article.content)
  return preview.length > 150 ? `${preview.slice(0, 150)}…` : preview
}

function matchesQuery(article: Article, loweredQuery: string) {
  if (!loweredQuery) {
    return true
  }

  return [
    safeTitle(article),
    article.content,
    article.date,
    article.sourceType,
  ]
    .join(' ')
    .toLowerCase()
    .includes(loweredQuery)
}

function compareArticles(left: Article, right: Article, sortMode: SortMode) {
  if (sortMode === 'date') {
    return right.date.localeCompare(left.date) || right.likes - left.likes
  }

  return right.likes - left.likes || right.date.localeCompare(left.date)
}

function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  const [query, setQuery] = useState('')
  const [sortMode, setSortMode] = useState<SortMode>('likes')
  const deferredQuery = useDeferredValue(query)
  const homeScrollY = useRef(0)

  useEffect(() => {
    const onHashChange = () => {
      startTransition(() => {
        setRoute(parseHash(window.location.hash))
      })
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (route.kind === 'home') {
      window.scrollTo({ top: homeScrollY.current, behavior: 'auto' })
      return
    }

    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [route])

  const navigate = (nextRoute: Route) => {
    const nextHash = nextRoute.kind === 'home' ? homeHash() : articleHash(nextRoute.id)

    if (window.location.hash === nextHash) {
      startTransition(() => {
        setRoute(nextRoute)
      })
      return
    }

    window.location.hash = nextHash
  }

  const homeArticles = useMemo(() => {
    const loweredQuery = deferredQuery.trim().toLowerCase()

    return [...payload.articles]
      .filter((article) => matchesQuery(article, loweredQuery))
      .sort((left, right) => compareArticles(left, right, sortMode))
  }, [deferredQuery, sortMode])

  const selectedArticle = useMemo(() => {
    if (route.kind !== 'article') {
      return null
    }

    return payload.articles.find((article) => article.id === route.id) ?? null
  }, [route])

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] text-[hsl(var(--foreground))]">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,_rgba(186,144,89,0.12),transparent_28%),radial-gradient(circle_at_top_right,_rgba(121,146,150,0.12),transparent_24%),linear-gradient(180deg,rgba(252,248,240,0.98),rgba(245,237,225,0.98))]" />

      {route.kind === 'home' ? (
        <HomePage
          articles={homeArticles}
          query={query}
          sortMode={sortMode}
          totalArticles={payload.totalArticles}
          totalImages={payload.totalImages}
          onArticleSelect={(id) => {
            homeScrollY.current = window.scrollY
            navigate({ kind: 'article', id })
          }}
          onQueryChange={setQuery}
          onSortChange={setSortMode}
        />
      ) : (
        <DetailPage
          article={selectedArticle}
          onBack={() => navigate({ kind: 'home' })}
        />
      )}
    </div>
  )
}

function HomePage({
  articles,
  query,
  sortMode,
  totalArticles,
  totalImages,
  onArticleSelect,
  onQueryChange,
  onSortChange,
}: {
  articles: Article[]
  query: string
  sortMode: SortMode
  totalArticles: number
  totalImages: number
  onArticleSelect: (id: number) => void
  onQueryChange: (value: string) => void
  onSortChange: (mode: SortMode) => void
}) {
  return (
    <main className="archive-main mx-auto flex w-full max-w-[1480px] flex-col gap-6 px-3 py-4 sm:gap-8 sm:px-6 sm:py-6 lg:px-10 lg:py-10">
      <section className="paper-panel hero-stage overflow-hidden px-4 py-5 sm:px-8 sm:py-8">
        <div className="hero-stage__content">
          <div className="archive-hero__top flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2.5 sm:space-y-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.36em] text-[hsl(var(--muted-foreground))]">
                VIDA Archive
              </div>
              <h1 className="archive-title max-w-4xl text-[2.45rem] font-semibold leading-[0.98] tracking-[0.01em] sm:text-4xl lg:text-[3.4rem]">
                00后富一代 VIDA
              </h1>
            </div>

            <div className="archive-stats flex flex-wrap items-center gap-2 text-xs text-[hsl(var(--muted-foreground))] sm:gap-3 sm:text-sm">
              <Badge variant="outline" className="rounded-full border-[rgba(82,59,38,0.14)] bg-white/85 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm">
                {totalArticles} 篇文章
              </Badge>
              <Badge variant="outline" className="rounded-full border-[rgba(82,59,38,0.14)] bg-white/85 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm">
                {totalImages} 张配图
              </Badge>
            </div>
          </div>

          <div className="archive-controls mt-4 flex flex-col gap-3 sm:mt-5 sm:gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full max-w-[720px]">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
              <Input
                className="h-11 rounded-full border-[rgba(82,59,38,0.14)] bg-white/90 pl-11 pr-4 text-sm shadow-none placeholder:text-[hsl(var(--muted-foreground))] sm:h-12"
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="搜索标题、内容、日期"
                value={query}
              />
            </div>

            <div className="archive-sort flex flex-wrap items-center gap-2.5 self-start lg:self-auto">
              <div className="rounded-full border border-[rgba(82,59,38,0.12)] bg-white/85 p-1">
                <SortButton
                  active={sortMode === 'likes'}
                  label="按点赞数"
                  onClick={() => onSortChange('likes')}
                />
                <SortButton
                  active={sortMode === 'date'}
                  label="按时间"
                  onClick={() => onSortChange('date')}
                />
              </div>
              <span className="archive-sort__count text-[13px] text-[hsl(var(--muted-foreground))] sm:text-sm">
                {articles.length} 条结果
              </span>
            </div>
          </div>
        </div>
      </section>

      {articles.length > 0 ? (
        <section className="grid min-w-0 gap-3.5 sm:gap-4 md:grid-cols-2 xl:grid-cols-3">
          {articles.map((article, index) => (
            <button
              key={article.id}
              className="article-card paper-panel group flex h-full min-w-0 flex-col px-4 py-4 text-left transition duration-200 hover:-translate-y-1 hover:border-[rgba(82,59,38,0.22)] hover:shadow-[0_24px_60px_rgba(56,35,18,0.11)] sm:px-5 sm:py-5"
              onClick={() => onArticleSelect(article.id)}
              type="button"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="rounded-full bg-[rgba(82,59,38,0.08)] px-3 py-1 text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  #{index + 1}
                </span>
                <Badge className="rounded-full bg-[rgba(82,59,38,0.9)] px-3 py-1 text-[11px] font-medium text-white hover:bg-[rgba(82,59,38,0.9)]">
                  {article.sourceType}
                </Badge>
              </div>

              <h2 className="article-card__title mt-3 text-[1.28rem] font-semibold leading-[1.34] tracking-[0.01em] transition-colors group-hover:text-[rgba(82,59,38,0.92)] sm:mt-4 sm:text-[1.5rem] sm:leading-[1.38]">
                {safeTitle(article)}
              </h2>

              <div className="article-card__meta mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-[hsl(var(--muted-foreground))] sm:mt-4 sm:gap-x-4 sm:gap-y-2 sm:text-sm">
                <span className="inline-flex items-center gap-1.5">
                  <ThumbsUp className="h-4 w-4" />
                  {formatLikes(article.likes)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="h-4 w-4" />
                  {article.date}
                </span>
              </div>

              <p className="article-card__preview mt-3 overflow-hidden text-[14px] leading-6 text-[hsl(var(--muted-foreground))] [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] sm:mt-4 sm:text-[15px] sm:leading-7 sm:[-webkit-line-clamp:3]">
                {previewText(article)}
              </p>
            </button>
          ))}
        </section>
      ) : (
        <section className="paper-panel flex min-h-[220px] items-center justify-center px-6 py-10 text-center text-[hsl(var(--muted-foreground))]">
          没有找到匹配的文章。
        </section>
      )}
    </main>
  )
}

function DetailPage({
  article,
  onBack,
}: {
  article: Article | null
  onBack: () => void
}) {
  return (
    <main className="mx-auto w-full max-w-[1040px] px-3 py-3 sm:px-6 sm:py-5 lg:px-8 lg:py-7">
      <div className="reading-surface overflow-hidden px-4 py-4 sm:px-8 sm:py-7">
        <div className="border-b border-[rgba(82,59,38,0.1)] pb-5">
          <Button
            className="rounded-full bg-transparent px-0 text-sm text-[hsl(var(--muted-foreground))] shadow-none hover:bg-transparent hover:text-[hsl(var(--foreground))] sm:text-base"
            onClick={onBack}
            type="button"
            variant="ghost"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回首页
          </Button>
        </div>

        {article ? (
          <article className="detail-article mx-auto mt-6 w-full max-w-[760px] sm:mt-8">
            <header className="border-b border-[rgba(82,59,38,0.1)] pb-5 sm:pb-6">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="rounded-full bg-[rgba(82,59,38,0.9)] px-3 py-1 text-white hover:bg-[rgba(82,59,38,0.9)]">
                  {article.sourceType}
                </Badge>
              </div>

              <h1 className="detail-title mt-4 text-[1.82rem] font-semibold leading-[1.16] tracking-[0.01em] sm:text-[3rem] sm:leading-[1.28]">
                {safeTitle(article)}
              </h1>

              <div className="detail-meta mt-4 flex flex-col items-start gap-2 text-[14px] text-[hsl(var(--muted-foreground))] sm:mt-5 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-5 sm:gap-y-2 sm:text-[15px]">
                <span className="inline-flex items-center gap-1.5">
                  <ThumbsUp className="h-4 w-4" />
                  {formatLikes(article.likes)} 赞同
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CalendarDays className="h-4 w-4" />
                  发布于 {article.date}
                </span>
              </div>
            </header>

            <div className="article-prose mt-6 sm:mt-8">
              {article.blocks.map((block, index) => {
                if (block.type === 'image') {
                  return (
                    <figure key={`${article.id}-image-${index}`} className="article-figure">
                      <img
                        alt={block.alt}
                        className="article-image"
                        loading="lazy"
                        src={block.src}
                      />
                    </figure>
                  )
                }

                return (
                  <p key={`${article.id}-text-${index}`}>{normalizeBlockText(block.text)}</p>
                )
              })}
            </div>
          </article>
        ) : (
          <div className="mx-auto flex min-h-[340px] max-w-[760px] flex-col items-center justify-center gap-5 px-4 text-center">
            <div className="text-3xl font-semibold">没有找到这篇文章</div>
            <p className="max-w-md text-[15px] leading-7 text-[hsl(var(--muted-foreground))]">
              当前链接对应的文章不存在，或者文章编号无效。
            </p>
            <Button className="rounded-full px-5" onClick={onBack} type="button">
              返回首页
            </Button>
          </div>
        )}
      </div>
    </main>
  )
}

function SortButton({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      className={`rounded-full px-3.5 py-1.5 text-[13px] transition sm:px-4 sm:py-2 sm:text-sm ${
        active
          ? 'bg-[rgba(82,59,38,0.92)] text-white shadow-[0_10px_24px_rgba(56,35,18,0.14)]'
          : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
      }`}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  )
}

export default App
