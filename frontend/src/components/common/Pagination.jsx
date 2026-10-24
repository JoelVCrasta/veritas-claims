"use client";

import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function PaginationBar({
  currentPage,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className="pagination-bar">
      <div className="pagination-info">
        <span>
          Showing <strong>{startItem}</strong> to <strong>{endItem}</strong> of <strong>{totalItems}</strong> entries
        </span>
        {onPageSizeChange && (
          <select
            className="pagination-size-select"
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value));
              onPageChange(1);
            }}
          >
            <option value={10}>10 per page</option>
            <option value={15}>15 per page</option>
            <option value={25}>25 per page</option>
            <option value={50}>50 per page</option>
          </select>
        )}
      </div>
      <div className="pagination-controls">
        <button
          className="pagination-btn"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          title="Previous page"
        >
          <ChevronLeft size={15} />
        </button>
        <span className="pagination-page-indicator">
          Page {currentPage} of {totalPages}
        </span>
        <button
          className="pagination-btn"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          title="Next page"
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}
