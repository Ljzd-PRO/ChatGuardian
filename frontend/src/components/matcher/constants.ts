import type { IconifyIcon } from '@iconify/react';
import addCircleBold from '@iconify/icons-solar/add-circle-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import checkSquareBold from '@iconify/icons-solar/check-square-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import closeCircleBold from '@iconify/icons-solar/close-circle-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import type { MatcherType } from '../../api/types';

export const TYPE_COLORS: Record<string, 'primary' | 'secondary' | 'danger' | 'default' | 'warning' | 'success'> = {
  and: 'primary',
  or: 'secondary',
  not: 'danger',
  all: 'success',
  sender: 'default',
  mention: 'default',
  chat: 'default',
  chat_type: 'warning',
  adapter: 'default',
};

export const MATCHER_ICONS: Record<MatcherType, IconifyIcon> = {
  and: checkSquareBold,
  or: addCircleBold,
  not: closeCircleBold,
  all: checkCircleBold,
  sender: userRoundedBold,
  mention: bellBingBold,
  chat: chatDotsBold,
  chat_type: usersGroupRoundedBold,
  adapter: plugCircleBold,
};
