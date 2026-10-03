/**
 * "Move to": one icon button that opens the places an item can go, the current one checked (Primer's
 * single-select ActionMenu; Things' Move dialog; Jira's Move). Choosing sends the move and asks nothing else.
 */
import { useId, useState } from 'react';
import { ListItemIcon, ListItemText, ListSubheader, Menu, MenuItem } from '@mui/material';
import { IconAction } from '../../shared/ui/IconAction';
import { CheckIcon, MoveIcon } from '../../shared/ui/icons';

export interface MoveDestination {
  value: string;
  label: string;
}

interface MoveMenuProps {
  /** Names the button, e.g. 移到其他職責. */
  label: string;
  /** Names the open menu, e.g. 移到職責. */
  heading: string;
  destinations: readonly MoveDestination[];
  /** The value of where the item is now; choosing it only closes the menu. */
  current: string;
  disabled: boolean;
  onMove: (value: string) => void;
}

export function MoveMenu({
  label,
  heading,
  destinations,
  current,
  disabled,
  onMove,
}: MoveMenuProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const menuId = useId();
  const open = anchor !== null;
  return (
    <>
      <IconAction
        label={label}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={(event) => setAnchor(event.currentTarget)}
      >
        <MoveIcon />
      </IconAction>
      <Menu
        id={menuId}
        anchorEl={anchor}
        open={open}
        onClose={() => setAnchor(null)}
        slotProps={{ list: { 'aria-label': heading, dense: true } }}
      >
        <ListSubheader role="presentation" disableSticky className="move-menu__heading">
          {heading}
        </ListSubheader>
        {destinations.map((destination) => {
          const isCurrent = destination.value === current;
          return (
            <MenuItem
              key={destination.value}
              role="menuitemradio"
              aria-checked={isCurrent}
              selected={isCurrent}
              onClick={() => {
                setAnchor(null);
                if (!isCurrent) onMove(destination.value);
              }}
            >
              <ListItemIcon>{isCurrent && <CheckIcon />}</ListItemIcon>
              <ListItemText>{destination.label}</ListItemText>
            </MenuItem>
          );
        })}
      </Menu>
    </>
  );
}
