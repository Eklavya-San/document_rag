import React from 'react';
import { MessageIcon, FileTextIcon, PlusIcon } from './Icons';

interface SidebarProps {
  activeTab: 'chat' | 'documents';
  setTab: (tab: 'chat' | 'documents') => void;
  onNewChat?: () => void;
}

export function Sidebar({ activeTab, setTab, onNewChat }: SidebarProps) {
  return (
    <aside className="app-sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        <PlusIcon size={18} />
        <span>New Conversation</span>
      </button>

      <nav className="nav-menu">
        <button
          className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setTab('chat')}
        >
          <MessageIcon size={18} />
          <span>Chat Workspace</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setTab('documents')}
        >
          <FileTextIcon size={18} />
          <span>Documents Library</span>
        </button>
      </nav>
    </aside>
  );
}
