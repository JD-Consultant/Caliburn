/**
 * A round button above the composer that takes the reader back to the newest message once they have scrolled
 * away from it (AI Elements' scroll button; ChatGPT and Claude show the same). The chat never pulls the view
 * down while someone reads older messages, so this is the way back.
 */
import { IconAction } from './IconAction';
import { ArrowDownIcon } from './icons';

export function JumpToLatest({ onClick }: { onClick: () => void }) {
  return (
    <IconAction label="回到最新訊息" className="jump-latest" onClick={onClick}>
      <ArrowDownIcon />
    </IconAction>
  );
}
