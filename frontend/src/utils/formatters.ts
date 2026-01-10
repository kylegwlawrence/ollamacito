import { format, formatDistanceToNow, isToday, isYesterday } from 'date-fns'

export const formatDate = (dateString: string): string => {
  const date = new Date(dateString)

  if (isToday(date)) {
    return format(date, 'HH:mm')
  }

  if (isYesterday(date)) {
    return `Yesterday ${format(date, 'HH:mm')}`
  }

  return format(date, 'MMM d, HH:mm')
}

export const formatRelativeTime = (dateString: string): string => {
  return formatDistanceToNow(new Date(dateString), { addSuffix: true })
}

export const formatModelName = (modelName: string): string => {
  return modelName.split(':')[0].replace(/-/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

export const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
