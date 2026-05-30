import Foundation
import Shared
import SwiftUI

// MARK: - Post onboarding

extension WebViewController {
    func postOnboardingNotificationPermission() {
        Current.Log.verbose("Skipping notification permission prompt in permission gateway build")
    }

    private func showNotificationPermissionRequest() {
        let view = NotificationPermissionRequestView().embeddedInHostingController()
        view.modalPresentationStyle = .overFullScreen
        view.view.backgroundColor = .clear
        view.modalTransitionStyle = .crossDissolve
        present(view, animated: true)
    }
}
