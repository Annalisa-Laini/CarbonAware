import pandas as pd
import matplotlib.pyplot as plt

class Plotter:
    def __init__(self, data, plot_type="seasonal", scale=False):
        self.data = data
        self.plot_type = plot_type
        self.scale = scale
    
    def plot_seasonal_scaled(self):
        """Plot the seasonal carbon intensity for each country."""
        # Group data and calculate the average carbon intensity per season per hour for each country
        hourly_avg_by_season = self.data.groupby(['country', 'season', 'hour']).mean().reset_index()

        # Order seasons
        season_order = ['Winter', 'Spring', 'Summer', 'Autumn']  # Season order
        hourly_avg_by_season['season'] = pd.Categorical(hourly_avg_by_season['season'], categories=season_order, ordered=True)

        season_colors = {
            'Winter': '#87CEEB',
            'Spring': 'green',
            'Summer': '#FFDB58',
            'Autumn': 'red'
        }

        unique_countries = hourly_avg_by_season['country'].unique()  # Subplots for each country
        
        # Define the number of columns for subplots
        ncols = 3
        nrows = (len(unique_countries) // ncols) + (len(unique_countries) % ncols > 0)  # Adjusting the number of rows
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(18, nrows * 5))  # Making subplots larger
        fig.set_constrained_layout_pads(
            wspace=0.06,  # width space between plots
            hspace=0.06  # height space between plots
        )
        axes = axes.flatten()  # Flatten axes array for easy indexing

        # Plot each country in a separate subplot
        for idx, country in enumerate(unique_countries):  # Seasonal data for each country
            ax = axes[idx]
            country_data = hourly_avg_by_season[hourly_avg_by_season['country'] == country]  # Filter data for the country
            country_renewable_avg = country_data['renewable percentage'].mean()


            # Plot each season's hourly data
            for season, color in season_colors.items():
                season_data = country_data[country_data['season'] == season]
                ax.plot(season_data['hour'], season_data['carbon intensity'], 
                        label=season, linestyle='-', marker='o', markersize=6, color=color)
            
            ax.set_title(f"{country}, avg Renewable: {country_renewable_avg:.2f}%", fontsize=14)
            ax.set_xlabel("Hour of the Day", fontsize=12)
            ax.set_ylabel("Carbon Intensity (gCO₂eq/kWh)", fontsize=12)
            if self.scale:
                    ax.set_ylim(0, 900)
            ax.grid(True, linestyle='--', alpha=0.6) 

        # Legend
        handles = [plt.Line2D([0], [0], color=color, lw=3) for color in season_colors.values()]
        labels = season_colors.keys()
        fig.legend(handles, labels, title="Season", loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=4, fontsize=12)

        # Layout adjustment to accommodate the legend at the top
        plt.tight_layout(rect=[0, 0, 1, 0.95])  # Making room for the legend at the top

        # Save and show the plot
        plt.savefig(r'energy_graphs\plots\seasonal_CI_trends_scaled.png', format='png', dpi=300)


    def plot_seasonal_not_scaled(self):
            """Plot the seasonal carbon intensity for each country."""
            # Group data and calculate the average carbon intensity per season per hour for each country
            hourly_avg_by_season = self.data.groupby(['country', 'season', 'hour']).mean().reset_index()

            # Order seasons
            season_order = ['Winter', 'Spring', 'Summer', 'Autumn']  # Season order
            hourly_avg_by_season['season'] = pd.Categorical(hourly_avg_by_season['season'], categories=season_order, ordered=True)
            
            season_colors = {
                'Winter': '#87CEEB',
                'Spring': 'green',
                'Summer': '#FFDB58',
                'Autumn': 'red'
            }

            unique_countries = hourly_avg_by_season['country'].unique()  # Subplots for each country

            # Define the number of columns for subplots
            ncols = 3
            nrows = (len(unique_countries) // ncols) + (len(unique_countries) % ncols > 0)  # Adjusting the number of rows
            fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(18, nrows * 5))  # Making subplots larger
            fig.set_constrained_layout_pads(
            wspace=0.06,  # width space between plots
            hspace=0.06  # height space between plots
            )
            axes = axes.flatten()  # Flatten axes array for easy indexing

            # Plot each country in a separate subplot
            for idx, country in enumerate(unique_countries):  # Seasonal data for each country
                ax = axes[idx]
                country_data = hourly_avg_by_season[hourly_avg_by_season['country'] == country]  # Filter data for the country
                country_renewable_avg = country_data['renewable percentage'].mean()

                # Plot each season's hourly data
                for season, color in season_colors.items():
                    season_data = country_data[country_data['season'] == season]
                    ax.plot(season_data['hour'], season_data['carbon intensity'], 
                            label=season, linestyle='-', marker='o', markersize=6, color=color)
                
                ax.set_title(f"{country}, avg Renewable: {country_renewable_avg:.2f}%", fontsize=18)
                ax.set_xlabel("Hour of the Day", fontsize=16)
                ax.set_ylabel("Carbon Intensity (gCO₂eq/kWh)", fontsize=16)
                ax.grid(True, linestyle='--', alpha=0.6) 

            # Legend
            handles = [plt.Line2D([0], [0], color=color, lw=3) for color in season_colors.values()]
            labels = season_colors.keys()
            fig.legend(handles, labels, title="Season", loc='upper center', bbox_to_anchor=(0.5, 1.02), ncol=4, fontsize=12)

            # Layout adjustment to accommodate the legend at the top
            plt.tight_layout(rect=[0, 0, 1, 0.95])  # Making room for the legend at the top

            # Save and show the plot
            plt.savefig(r'energy_graphs\plots\seasonal_CI_trends.png', format='png', dpi=300) 


    def plot_monthly_scaled(self):
        """Plot the monthly carbon intensity for each country."""
        month_names = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
            7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
        }
        colors = [
            '#4fa3f7', '#003366', '#8fbc8f', '#007f66', '#8bbe1b', '#ffff00', 
            '#ff9800', '#ff5733', '#8b4513', '#b48e63', '#4b3621', '#006699'
        ]

        unique_countries = self.data['country'].unique()  # List of unique countries

        # Set up the grid for subplots
        n_countries = len(unique_countries)
        ncols = 3  # Number of columns in the grid
        nrows = -(-n_countries // ncols)  # Calculate the required number of rows

        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(23, 7 * nrows), constrained_layout=True)
        fig.set_constrained_layout_pads(
            wspace=0.1,  # width space between plots
            hspace=0.1  # height space between plots
        )
        axes = axes.flatten()  # Flatten axes for easier indexing

        # Loop through each country and create subplots
        for i, country in enumerate(unique_countries):
            ax = axes[i]  # Get the axis for this subplot
            country_data = self.data[self.data['country'] == country]

            # Calculate the general renewable percentage for the country
            country_renewable_avg = country_data['renewable percentage'].mean()

            # Calculate hourly average carbon intensity for each month
            hourly_avg_by_month = country_data.groupby(['month', 'hour']).mean(numeric_only=True).reset_index()

            # Plot the data for each month
            for month, color in zip(range(1, 13), colors):
                month_data = hourly_avg_by_month[hourly_avg_by_month['month'] == month]
                ax.plot(month_data['hour'], month_data['carbon intensity'], 
                        label=month_names[month], color=color, marker='o')

            # Set subplot titles and labels
                ax.set_title(f"{country}, avg Renewable: {country_renewable_avg:.2f}%", fontsize=20, fontweight='bold')
                ax.set_xlabel("Hour of the Day", fontsize=16)
                ax.set_ylabel("Carbon Intensity (gCO₂eq/kWh)", fontsize=16)
                # print(f"scale is {self.scale}")  # Check if scale is True or False
                if self.scale:
                    ax.set_ylim(0, 900)                
                ax.grid(True, linestyle='--', alpha=0.6)
                #ax.legend(fontsize=12, loc='upper right', title="Month")
                ax.legend(
                loc='upper center',      # Pins the top-middle of the legend box...
                bbox_to_anchor=(0.5, -0.15), # ...to the bottom-center of the plot (x=0.5, y=-0.15)
                ncol=3,                  # Splits the legend into 3 columns (adjust as needed)
                fontsize=16,
                title="Month",
                title_fontsize=16,
                frameon=False            # Optional: removes the box border for a cleaner look
            )


        # Hide unused subplots
        for j in range(i + 1, len(axes)):
            fig.delaxes(axes[j])

        # Save and show the plot
        plt.savefig(r'energy_graphs\plots\monthly_CI_trends_scaled.png', format='png', dpi=300)
    
    def plot_monthly_not_scaled(self):
            """Plot the monthly carbon intensity for each country."""
            month_names = {
                1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
            }
            colors = [
                '#4fa3f7', '#003366', '#8fbc8f', '#007f66', '#8bbe1b', '#ffff00', 
                '#ff9800', '#ff5733', '#8b4513', '#b48e63', '#4b3621', '#006699'
            ]

            unique_countries = self.data['country'].unique()  # List of unique countries

            # Set up the grid for subplots
            n_countries = len(unique_countries)
            ncols = 3  # Number of columns in the grid
            nrows = -(-n_countries // ncols)  # Calculate the required number of rows

            fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(18, 5 * nrows), constrained_layout=True)
            fig.set_constrained_layout_pads(
            wspace=0.06,  # width space between plots
            hspace=0.06  # height space between plots
                )
            axes = axes.flatten()  # Flatten axes for easier indexing

            # Loop through each country and create subplots
            for i, country in enumerate(unique_countries):
                ax = axes[i]  # Get the axis for this subplot
                country_data = self.data[self.data['country'] == country]
                

                # Calculate the general renewable percentage for the country
                country_renewable_avg = country_data['renewable percentage'].mean()

                # Calculate hourly average carbon intensity for each month
                hourly_avg_by_month = country_data.groupby(['month', 'hour']).mean(numeric_only=True).reset_index()

                # Plot the data for each month
                for month, color in zip(range(1, 13), colors):
                    month_data = hourly_avg_by_month[hourly_avg_by_month['month'] == month]
                    ax.plot(month_data['hour'], month_data['carbon intensity'], 
                            label=month_names[month], color=color, marker='o')

                # Set subplot titles and labels
                ax.set_title(f"{country}, avg Renewable: {country_renewable_avg:.2f}%", fontsize=18)
                ax.set_xlabel("Hour of the Day", fontsize=16)
                ax.set_ylabel("Carbon Intensity (gCO₂eq/kWh)", fontsize=16)
                # ax.set_ylim(0, 900)
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.legend(fontsize=10, loc='upper right', title="Month")
                

            # Hide unused subplots
            for j in range(i + 1, len(axes)):
                fig.delaxes(axes[j])

            # Save and show the plot
            plt.savefig(r'energy_graphs\plots\monthly_CI_trends.png', format='png', dpi=300)
    
    def plot_data(self):
        if self.plot_type == "seasonal":
            if self.scale:
                self.plot_seasonal_scaled()  # Plot seasonal data with scaling
            else:
                self.plot_seasonal_not_scaled()  # Plot seasonal data without scaling
        elif self.plot_type == "monthly":
            if self.scale:
                self.plot_monthly_scaled()  # Plot monthly data with scaling
            else:
                self.plot_monthly_not_scaled()  # Plot monthly data without scaling