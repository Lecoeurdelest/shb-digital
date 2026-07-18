// ErrorBoundary.tsx — bắt render error (React error boundary — chỉ class component làm được).
// Fallback UI thay vì trắng màn + nút tải lại. Bọc App để 1 lỗi render 1 màn không sập cả app.
import { Component, type ErrorInfo, type ReactNode } from 'react';
import './ErrorBoundary.css';

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // log (production: gửi telemetry). Dev: giúp debug — không nuốt im.
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] render error:', error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="errbound" role="alert">
          <div className="errbound__box">
            <div className="errbound__icon">⚠</div>
            <div className="errbound__title">Giao diện gặp lỗi</div>
            <div className="errbound__msg">
              Một phần màn hình không hiển thị được. Tải lại trang để tiếp tục — dữ liệu đã lưu ở máy chủ không mất.
            </div>
            <pre className="errbound__detail">{this.state.error.message}</pre>
            <button type="button" className="btn btn--primary errbound__reload" onClick={this.reset}>
              ⟳ Tải lại trang
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
